package com.portfolio.investigation.application;

import java.util.UUID;
import com.portfolio.investigation.domain.Investigation;

/** Application port; no Python, HTTP or graph implementation types escape this boundary. */
public interface AgentGateway {
    Investigation create(String question, String correlationId);
    Investigation get(UUID investigationId, String correlationId);
}
