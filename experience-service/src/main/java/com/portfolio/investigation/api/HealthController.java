package com.portfolio.investigation.api;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
    public record Health(String status, String service) {}
    /** Liveness only; agent availability is intentionally independent. */
    @GetMapping("/api/v1/health")
    public Health health() { return new Health("UP", "experience-service"); }
}
