package com.portfolio.investigation;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.http.MediaType;
import org.slf4j.MDC;
import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@org.junit.jupiter.api.extension.ExtendWith(org.springframework.boot.test.system.OutputCaptureExtension.class)
@SpringBootTest
@AutoConfigureMockMvc
class ApiIntegrationTest {
    // Test-only real HTTP server exercises serialization, networking and error handling.
    static final AtomicInteger status = new AtomicInteger(200);
    static final AtomicInteger calls = new AtomicInteger();
    static final AtomicInteger delay = new AtomicInteger();
    static final AtomicReference<String> response = new AtomicReference<>(Fixtures.json());
    static final AtomicReference<String> header = new AtomicReference<>();
    static final AtomicReference<String> body = new AtomicReference<>();
    static final AtomicReference<String> path = new AtomicReference<>();
    static final java.util.concurrent.ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
    static final HttpServer server = start();
    static HttpServer start() {
        try {
            HttpServer s = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            s.setExecutor(executor);
            s.createContext("/", exchange -> {
                calls.incrementAndGet();
                header.set(exchange.getRequestHeaders().getFirst("X-Correlation-Id"));
                body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
                path.set(exchange.getRequestURI().getPath());
                int code = status.get();
                byte[] bytes = response.get().getBytes(StandardCharsets.UTF_8);
                try {
                    Thread.sleep(delay.get());
                    exchange.getResponseHeaders().set("Content-Type", "application/json");
                    exchange.sendResponseHeaders(code, bytes.length);
                    exchange.getResponseBody().write(bytes);
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { exchange.close(); }
            });
            s.start(); return s;
        } catch (IOException e) { throw new java.io.UncheckedIOException(e); }
    }
    @DynamicPropertySource static void properties(DynamicPropertyRegistry registry) {
        registry.add("agent.base-url", () -> "http://127.0.0.1:"+server.getAddress().getPort());
        registry.add("agent.connect-timeout", () -> "1s");
        registry.add("agent.request-timeout", () -> "2s");
    }
    @Autowired MockMvc mvc;
    @BeforeEach void reset() {
        status.set(200); calls.set(0); delay.set(0); response.set(Fixtures.json());
        body.set(null); header.set(null); path.set(null);
    }
    @AfterAll static void stop() { server.stop(0); executor.shutdownNow(); }
    @Test void createPropagatesCorrelationAndNormalizesQuestion(org.springframework.boot.test.system.CapturedOutput output) throws Exception {
        String trace = UUID.randomUUID().toString();
        mvc.perform(post("/api/v1/investigations").header("X-Correlation-Id", trace)
            .contentType(MediaType.APPLICATION_JSON).content("{\"question\":\"  Why did volume decline?  \"}"))
            .andExpect(status().isCreated()).andExpect(header().string("X-Correlation-Id", trace))
            .andExpect(header().string("Location", "/api/v1/investigations/"+Fixtures.ID))
            .andExpect(jsonPath("$.investigationId").value(Fixtures.ID.toString()))
            .andExpect(jsonPath("$.status").value("completed"))
            .andExpect(jsonPath("$.question").value(Fixtures.QUESTION))
            .andExpect(jsonPath("$.createdAt").value("2026-06-22T01:00:00Z"));
        assertThat(header.get()).isEqualTo(trace);
        assertThat(path.get()).isEqualTo("/internal/v1/investigations");
        assertThat(body.get()).contains("Why did volume decline?").doesNotContain("  Why");
        assertThat(calls.get()).isEqualTo(1);
        assertThat(output.getAll()).contains("\"event\":\"agent_request\"")
            .contains("\"event\":\"investigation_response\"").doesNotContain("failed to append");
        assertThat(MDC.get("correlationId")).isNull();
    }
    @Test void getReturnsFullResult() throws Exception {
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID))
            .andExpect(status().isOk()).andExpect(jsonPath("$.summary").exists())
            .andExpect(jsonPath("$.findings[0].evidenceIds[0]").value("e1"))
            .andExpect(jsonPath("$.evidence[0].rows[0][0]").value(700))
            .andExpect(jsonPath("$.sqlQueries[0].rowCount").value(1))
            .andExpect(jsonPath("$.toolExecutions[0].toolName").value("execute_readonly_sql"))
            .andExpect(jsonPath("$.completedAt").exists());
        assertThat(path.get()).endsWith(Fixtures.ID.toString());
        assertThat(header.get()).isNotNull();
    }
    @Test void pendingReturnsAcceptedNotFakeCompletion() throws Exception {
        response.set(Fixtures.json().replaceFirst("completed", "pending").replace("\"2026-06-22T01:00:02Z\"", "null"));
        mvc.perform(post("/api/v1/investigations").contentType(MediaType.APPLICATION_JSON)
            .content("{\"question\":\"Why did volume decline?\"}"))
            .andExpect(status().isAccepted()).andExpect(jsonPath("$.status").value("pending"));
    }
    @ParameterizedTest @ValueSource(strings={"{}", "{\"question\":null}", "{\"question\":\"   \"}", "{broken", "{\"question\":\"x\",\"extra\":1}"})
    void invalidRequestsNeverCallAgent(String input) throws Exception {
        mvc.perform(post("/api/v1/investigations").contentType(MediaType.APPLICATION_JSON).content(input))
            .andExpect(status().isBadRequest()).andExpect(jsonPath("$.error.code").value("INVALID_REQUEST"))
            .andExpect(jsonPath("$.correlationId").exists());
        assertThat(calls.get()).isZero();
    }
    @Test void rejectsTooLongQuestion() throws Exception {
        mvc.perform(post("/api/v1/investigations").contentType(MediaType.APPLICATION_JSON)
            .content("{\"question\":\""+"x".repeat(2001)+"\"}"))
            .andExpect(status().isBadRequest());
        assertThat(calls.get()).isZero();
    }
    @Test void malformedIdIsBadRequest() throws Exception {
        mvc.perform(get("/api/v1/investigations/not-a-uuid")).andExpect(status().isBadRequest());
        assertThat(calls.get()).isZero();
    }
    @Test void healthDoesNotDependOnAgent() throws Exception {
        mvc.perform(get("/api/v1/health")).andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("UP"));
        assertThat(calls.get()).isZero();
    }
    @Test void invalidCorrelationIsReplacedAndDoesNotLeakBetweenRequests() throws Exception {
        var a = mvc.perform(get("/api/v1/health").header("X-Correlation-Id", "bad-id"))
            .andReturn().getResponse().getHeader("X-Correlation-Id");
        var b = mvc.perform(get("/api/v1/health")).andReturn().getResponse().getHeader("X-Correlation-Id");
        assertThat(UUID.fromString(a)).isNotEqualTo(UUID.fromString(b));
        assertThat(MDC.get("correlationId")).isNull();
    }
    @Test void downstreamNotFoundIsNormalized() throws Exception {
        status.set(404); response.set("private downstream details");
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error.code").value("INVESTIGATION_NOT_FOUND"))
            .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("private"))));
    }
    @ParameterizedTest @ValueSource(ints={400,401,403,404,500})
    void failedCreateIsBadGatewayWithoutRetries(int code) throws Exception {
        status.set(code); response.set("sensitive-provider-error");
        mvc.perform(post("/api/v1/investigations").contentType(MediaType.APPLICATION_JSON)
            .content("{\"question\":\"Why did volume decline?\"}"))
            .andExpect(status().isBadGateway()).andExpect(jsonPath("$.error.code").value("AGENT_BAD_RESPONSE"));
        assertThat(calls.get()).isEqualTo(1);
    }
    @ParameterizedTest @ValueSource(ints={429,503})
    void unavailableIs503(int code) throws Exception {
        status.set(code);
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isServiceUnavailable());
    }
    @Test void deadlineIs504WithoutRetry() throws Exception {
        delay.set(2500);
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isGatewayTimeout())
            .andExpect(jsonPath("$.error.code").value("AGENT_TIMEOUT"));
        assertThat(calls.get()).isEqualTo(1);
    }
    @Test void malformedSuccessBodyIs502() throws Exception {
        response.set("not-json");
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isBadGateway());
    }
    @Test void mismatchedResultIdIs502() throws Exception {
        mvc.perform(get("/api/v1/investigations/"+UUID.randomUUID())).andExpect(status().isBadGateway());
    }
    @Test void failedInvestigationHasSanitizedError() throws Exception {
        response.set(Fixtures.json().replaceFirst("completed", "failed"));
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isOk())
            .andExpect(jsonPath("$.error.code").value("INVESTIGATION_FAILED"));
    }
    @ParameterizedTest @ValueSource(strings={"{\"question\":1}", "{\"question\":true}", "{\"question\":[]}"})
    void questionMustBeAString(String input) throws Exception {
        mvc.perform(post("/api/v1/investigations").contentType(MediaType.APPLICATION_JSON).content(input))
            .andExpect(status().isBadRequest());
        assertThat(calls.get()).isZero();
    }
    @Test void downstreamWrongQuestionIsRejected() throws Exception {
        mvc.perform(post("/api/v1/investigations").contentType(MediaType.APPLICATION_JSON)
            .content("{\"question\":\"A different question\"}"))
            .andExpect(status().isBadGateway());
    }
    @Test void invalidDownstreamShapeIsRejected() throws Exception {
        response.set("{}");
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isBadGateway());
    }
    @Test void errorCorrelationMatchesHeader() throws Exception {
        String trace = UUID.randomUUID().toString();
        status.set(504);
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID).header("X-Correlation-Id", trace))
            .andExpect(status().isGatewayTimeout()).andExpect(header().string("X-Correlation-Id", trace))
            .andExpect(jsonPath("$.correlationId").value(trace));
    }
    @Test void oversizedAgentPayloadIsRejected() throws Exception {
        response.set("{\"padding\":\""+"x".repeat(1024*1024)+"\"}");
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isBadGateway());
    }
    @Test void openApiIsServedWithoutCallingAgent() throws Exception {
        mvc.perform(get("/openapi.json")).andExpect(status().isOk())
            .andExpect(jsonPath("$.openapi").value("3.1.0"))
            .andExpect(jsonPath("$.components.schemas.Result.properties.confidence.type").value("number"));
        assertThat(calls.get()).isZero();
    }
    @Test void inconsistentEvidenceCountIsRejected() throws Exception {
        response.set(Fixtures.json().replace("\"rowCount\":1", "\"rowCount\":2"));
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isBadGateway());
    }
    @Test void mismatchedIdentityIsLoggedAsBadResponse(org.springframework.boot.test.system.CapturedOutput output) throws Exception {
        mvc.perform(get("/api/v1/investigations/"+UUID.randomUUID())).andExpect(status().isBadGateway());
        assertThat(output.getAll()).contains("\"outcome\":\"BAD_RESPONSE\"");
    }
    @Test void privatePythonFieldsAreNotExposed() throws Exception {
        response.set(Fixtures.json().replace("\"summary\":", "\"currentStep\":\"synthesize_findings\",\"errors\":[\"private-provider-detail\"],\"summary\":"));
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isOk())
            .andExpect(jsonPath("$.currentStep").doesNotExist()).andExpect(jsonPath("$.errors").doesNotExist())
            .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("private-provider-detail"))));
    }
    @Test void failedCreateStillReturnsRetrievableInvestigation() throws Exception {
        response.set(Fixtures.json().replaceFirst("completed", "failed"));
        mvc.perform(post("/api/v1/investigations").contentType(MediaType.APPLICATION_JSON)
            .content("{\"question\":\"Why did volume decline?\"}"))
            .andExpect(status().isCreated()).andExpect(jsonPath("$.status").value("failed"));
    }
    @Test void partialResultPreservesEvidence() throws Exception {
        response.set(Fixtures.json().replaceFirst("completed", "partial"));
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("partial"))
            .andExpect(jsonPath("$.evidence[0].rows[0][0]").value(700));
    }
    @Test void emptySuccessBodyIsBadGateway() throws Exception {
        response.set("");
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isBadGateway());
    }
    @Test void redirectIsNotFollowed() throws Exception {
        status.set(302);
        mvc.perform(get("/api/v1/investigations/"+Fixtures.ID)).andExpect(status().isBadGateway());
        assertThat(calls.get()).isEqualTo(1);
    }
}
