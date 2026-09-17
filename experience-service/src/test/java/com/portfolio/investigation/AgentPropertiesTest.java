package com.portfolio.investigation;

import java.net.URI;
import java.time.Duration;
import jakarta.validation.Validation;
import org.junit.jupiter.api.Test;
import com.portfolio.investigation.config.AgentProperties;
import static org.assertj.core.api.Assertions.*;

class AgentPropertiesTest {
    @Test void rejectsCredentialUrlsAndInvalidBudgets() {
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var validator = factory.getValidator();
            assertThat(validator.validate(new AgentProperties(URI.create("http://user:secret@host"),
                Duration.ofSeconds(2), Duration.ofSeconds(65)))) .isNotEmpty();
            assertThat(validator.validate(new AgentProperties(URI.create("http://localhost:8000"),
                Duration.ZERO, Duration.ofSeconds(65)))).isNotEmpty();
            assertThat(validator.validate(new AgentProperties(URI.create("http://localhost:8000"),
                Duration.ofSeconds(2), Duration.ofSeconds(65)))).isEmpty();
        }
    }
}
