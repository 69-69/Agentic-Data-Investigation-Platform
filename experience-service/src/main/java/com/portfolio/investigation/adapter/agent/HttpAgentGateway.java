package com.portfolio.investigation.adapter.agent;

import java.util.UUID;
import java.util.concurrent.TimeoutException;
import io.netty.channel.ChannelOption;
import io.netty.channel.ConnectTimeoutException;
import io.netty.handler.timeout.ReadTimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;
import com.portfolio.investigation.application.AgentGateway;
import com.portfolio.investigation.application.ServiceFailure;
import com.portfolio.investigation.config.AgentProperties;
import com.portfolio.investigation.domain.Investigation;
import static com.portfolio.investigation.application.ServiceFailure.Kind.*;

@Component
public class HttpAgentGateway implements AgentGateway {
    private static final Logger log = LoggerFactory.getLogger(HttpAgentGateway.class);
    private final WebClient client;
    private final AgentProperties properties;
    private final AgentMapper mapper;
    public HttpAgentGateway(WebClient.Builder builder, AgentProperties properties, AgentMapper mapper) {
        this.properties = properties;
        this.mapper = mapper;
        var http = HttpClient.create().disableRetry(true)
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, (int) properties.connectTimeout().toMillis())
                .responseTimeout(properties.requestTimeout());
        this.client = builder.baseUrl(properties.baseUrl().toString())
                .clientConnector(new ReactorClientHttpConnector(http))
                .codecs(c -> c.defaultCodecs().maxInMemorySize(1024 * 1024)).build();
    }
    public Investigation create(String question, String correlationId) {
        return execute(client.post().uri("/internal/v1/investigations")
            .contentType(MediaType.APPLICATION_JSON).bodyValue(new AgentPayload.Create(question)), correlationId, null, question);
    }
    public Investigation get(UUID id, String correlationId) {
        return execute(client.get().uri("/internal/v1/investigations/{id}", id), correlationId, id, null);
    }
    private Investigation execute(WebClient.RequestHeadersSpec<?> request, String correlationId, UUID expectedId, String expectedQuestion) {
        long start = System.nanoTime();
        String outcome = "success";
        try {
            AgentPayload payload = request.header("X-Correlation-Id", correlationId).accept(MediaType.APPLICATION_JSON)
                .exchangeToMono(response -> {
                    int status = response.statusCode().value();
                    if (status >= 200 && status < 300) return response.bodyToMono(AgentPayload.class);
                    var kind = status == 404 && expectedId != null ? NOT_FOUND
                        : status == 429 || status == 503 ? UNAVAILABLE : status == 504 ? TIMEOUT : BAD_RESPONSE;
                    // Discard error bodies: do not deserialize, expose or log provider details.
                    return response.releaseBody().then(Mono.error(new ServiceFailure(kind)));
                }).timeout(properties.requestTimeout()).block();
            var result = mapper.map(payload);
            if ((expectedId != null && !expectedId.equals(result.id()))
                    || (expectedQuestion != null && !expectedQuestion.equals(result.question())))
                throw new ServiceFailure(BAD_RESPONSE);
            outcome = result.status().name();
            return result;
        } catch (ServiceFailure e) {
            outcome = e.kind().name(); throw e;
        } catch (RuntimeException e) {
            var kind = causedByTimeout(e) ? TIMEOUT : e instanceof WebClientRequestException ? UNAVAILABLE : BAD_RESPONSE;
            outcome = kind.name(); throw new ServiceFailure(kind);
        } finally {
            var event = log.atInfo().addKeyValue("event", "agent_request")
                .addKeyValue("operation", expectedId == null ? "create" : "get")
                .addKeyValue("outcome", outcome).addKeyValue("durationMs", (System.nanoTime()-start)/1_000_000);
            // The servlet MDC already supplies this key; duplicate keys break JSON logging.
            if (org.slf4j.MDC.get("correlationId") == null) event.addKeyValue("correlationId", correlationId);
            event.log("Agent request finished");
        }
    }
    private boolean causedByTimeout(Throwable error) {
        for (Throwable t = error; t != null; t = t.getCause())
            if (t instanceof TimeoutException || t instanceof ReadTimeoutException || t instanceof ConnectTimeoutException) return true;
        return false;
    }
}
