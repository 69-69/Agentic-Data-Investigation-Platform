package com.portfolio.investigation.adapter.agent;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.Locale;
import org.springframework.stereotype.Component;
import jakarta.validation.Validator;
import com.portfolio.investigation.application.ServiceFailure;
import com.portfolio.investigation.domain.Investigation;
import static com.portfolio.investigation.application.ServiceFailure.Kind.BAD_RESPONSE;

@Component
public class AgentMapper {
    private final Validator validator;
    public AgentMapper(Validator validator) { this.validator = validator; }
    public Investigation map(AgentPayload p) {
        if (p == null || !validator.validate(p).isEmpty()) throw new ServiceFailure(BAD_RESPONSE);
        Investigation.Status status;
        try { status = Investigation.Status.valueOf(p.status().toUpperCase(Locale.ROOT)); }
        catch (IllegalArgumentException e) { throw new ServiceFailure(BAD_RESPONSE); }
        boolean terminal = status != Investigation.Status.PENDING && status != Investigation.Status.RUNNING;
        if (terminal != (p.completedAt() != null)
                || (p.completedAt() != null && p.completedAt().isBefore(p.createdAt())))
            throw new ServiceFailure(BAD_RESPONSE);
        Set<String> sqlIds = unique(p.sqlQueries().stream().map(AgentPayload.SqlQuery::id).toList());
        Set<String> evidenceIds = unique(p.evidence().stream().map(AgentPayload.Evidence::id).toList());
        unique(p.findings().stream().map(AgentPayload.Finding::id).toList());
        unique(p.toolExecutions().stream().map(AgentPayload.ToolExecution::id).toList());
        for (var e : p.evidence()) {
            if (!sqlIds.contains(e.sqlQueryId()) || e.rows().stream().anyMatch(row -> row.size() != e.columns().size()))
                throw new ServiceFailure(BAD_RESPONSE);
        }
        for (var e : p.evidence()) {
            var query = p.sqlQueries().stream().filter(q -> q.id().equals(e.sqlQueryId())).findFirst().orElseThrow();
            if (query.rowCount() != e.rows().size()
                    || (e.rowCount() != null && e.rowCount() != e.rows().size())
                    || (e.query() != null && !e.query().equals(query.sql())))
                throw new ServiceFailure(BAD_RESPONSE);
        }
        for (var f : p.findings()) if (f.evidenceIds().isEmpty() || !evidenceIds.containsAll(f.evidenceIds())) throw new ServiceFailure(BAD_RESPONSE);
        for (var t : p.toolExecutions()) if (t.completedAt().isBefore(t.startedAt())) throw new ServiceFailure(BAD_RESPONSE);
        return new Investigation(p.investigationId(), status, p.question(), p.summary(),
            p.findings().stream().map(f -> new Investigation.Finding(f.id(), f.description(), List.copyOf(f.evidenceIds()), f.title() == null ? "Observation" : f.title(), f.confidence() == null ? 0.0 : f.confidence())).toList(),
            p.evidence().stream().map(e -> new Investigation.Evidence(e.id(), e.description(), e.sqlQueryId(), e.columns(), e.rows(), "sql_result",
                p.sqlQueries().stream().filter(q -> q.id().equals(e.sqlQueryId())).findFirst().orElseThrow().sql(), e.rows().size())).toList(),
            p.sqlQueries().stream().map(s -> new Investigation.SqlQuery(s.id(), s.sql(), s.rowCount(), s.truncated())).toList(),
            p.toolExecutions().stream().map(t -> new Investigation.ToolExecution(t.id(), t.toolName(), t.status(), t.startedAt(), t.completedAt(), t.durationMs())).toList(),
            p.createdAt(), p.completedAt(), status == Investigation.Status.FAILED
                ? new Investigation.Failure("INVESTIGATION_FAILED", "The investigation could not be completed.") : null, p.probableRootCause(), p.confidence() == null ? 0.0 : p.confidence());
    }
    private Set<String> unique(List<String> values) {
        Set<String> set = new HashSet<>(values);
        if (set.size() != values.size()) throw new ServiceFailure(BAD_RESPONSE);
        return set;
    }
}
