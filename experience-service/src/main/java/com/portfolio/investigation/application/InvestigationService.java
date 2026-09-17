package com.portfolio.investigation.application;

import java.util.UUID;
import org.springframework.stereotype.Service;
import com.portfolio.investigation.domain.Investigation;

@Service
public class InvestigationService {
    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(InvestigationService.class);
    private final AgentGateway agent;
    public InvestigationService(AgentGateway agent) { this.agent = agent; }
    public Investigation create(String question, String correlationId) {
        return observed(agent.create(question, correlationId), correlationId);
    }
    public Investigation get(UUID id, String correlationId) {
        return observed(agent.get(id, correlationId), correlationId);
    }
    private Investigation observed(Investigation result, String correlationId) {
        log.atInfo().addKeyValue("event", "investigation_response").addKeyValue("investigationId", result.id())
            .addKeyValue("status", result.status().name())
            .log("Investigation response received");
        return result;
    }
}
