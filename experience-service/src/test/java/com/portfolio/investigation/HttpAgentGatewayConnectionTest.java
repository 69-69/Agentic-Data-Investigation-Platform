package com.portfolio.investigation;

import java.net.URI;
import java.net.ServerSocket;
import java.time.Duration;
import java.util.UUID;
import jakarta.validation.Validation;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;
import com.portfolio.investigation.adapter.agent.*;
import com.portfolio.investigation.application.ServiceFailure;
import com.portfolio.investigation.config.AgentProperties;
import static org.assertj.core.api.Assertions.*;

class HttpAgentGatewayConnectionTest {
    @Test void refusedConnectionHasSafeUnavailableClassification() throws Exception {
        int port;
        try (var socket = new ServerSocket(0)) { port = socket.getLocalPort(); }
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var properties = new AgentProperties(URI.create("http://127.0.0.1:"+port), Duration.ofSeconds(1), Duration.ofSeconds(2));
            var gateway = new HttpAgentGateway(WebClient.builder(), properties, new AgentMapper(factory.getValidator()));
            assertThatThrownBy(() -> gateway.get(Fixtures.ID, UUID.randomUUID().toString()))
                .isInstanceOfSatisfying(ServiceFailure.class, e -> {
                    assertThat(e.kind()).isEqualTo(ServiceFailure.Kind.UNAVAILABLE);
                    assertThat(e.getMessage()).isEqualTo("UNAVAILABLE");
                    assertThat(e.getCause()).isNull();
                });
        }
    }
}
