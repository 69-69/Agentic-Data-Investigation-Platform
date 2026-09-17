package com.portfolio.investigation.config;

import java.net.URI;
import java.time.Duration;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("agent")
public record AgentProperties(@NotNull URI baseUrl, @NotNull Duration connectTimeout,
                              @NotNull Duration requestTimeout) {
    @AssertTrue(message = "agent URL must be an HTTP(S) origin without credentials, query, path or fragment")
    public boolean isValidUrl() {
        return baseUrl != null && ("http".equals(baseUrl.getScheme()) || "https".equals(baseUrl.getScheme()))
                && baseUrl.getHost() != null && baseUrl.getUserInfo() == null
                && baseUrl.getQuery() == null && baseUrl.getFragment() == null
                && (baseUrl.getPath().isEmpty() || "/".equals(baseUrl.getPath()));
    }
    @AssertTrue(message = "timeouts must be positive, connect <= request, request <= 90 seconds")
    public boolean isValidTimeouts() {
        return connectTimeout != null && requestTimeout != null
                && connectTimeout.toMillis() >= 1 && requestTimeout.toMillis() >= 1
                && connectTimeout.compareTo(requestTimeout) <= 0
                && requestTimeout.compareTo(Duration.ofSeconds(90)) <= 0;
    }
}
