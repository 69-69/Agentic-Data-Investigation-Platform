package com.portfolio.investigation.api;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import com.portfolio.investigation.domain.Investigation;

public final class ApiDtos {
    private ApiDtos() {}
    public record CreateRequest(@NotBlank @Size(max=2000) String question) {
        public CreateRequest { if (question != null) question = question.strip(); }
    }
    public record Created(UUID investigationId, String status, String question, Instant createdAt) {}
    public record Result(UUID investigationId, String status, String question, String summary,
        List<Finding> findings, List<Evidence> evidence, List<SqlQuery> sqlQueries,
        List<ToolExecution> toolExecutions, Instant createdAt, Instant completedAt, ErrorDetail error, String probableRootCause, double confidence) {}
    public record Finding(String id, String description, List<String> evidenceIds, String title, double confidence) {}
    public record Evidence(String id, String description, String sqlQueryId, List<String> columns, List<List<Object>> rows, String type, String query, int rowCount) {}
    public record SqlQuery(String id, String sql, int rowCount, boolean truncated) {}
    public record ToolExecution(String id, String toolName, String status, Instant startedAt, Instant completedAt, long durationMs) {}
    public record ErrorDetail(String code, String message) {}
    public record ErrorResponse(ErrorDetail error, String correlationId) {}
    public static Created created(Investigation i) { return new Created(i.id(), status(i), i.question(), i.createdAt()); }
    private static String status(Investigation i) { return i.status().name().toLowerCase(Locale.ROOT); }
    public static Result result(Investigation i) {
        return new Result(i.id(), status(i), i.question(), i.summary(),
            i.findings().stream().map(f -> new Finding(f.id(), f.description(), f.evidenceIds(), f.title(), f.confidence())).toList(),
            i.evidence().stream().map(e -> new Evidence(e.id(), e.description(), e.sqlQueryId(), e.columns(), e.rows(), e.type(), e.query(), e.rowCount())).toList(),
            i.sqlQueries().stream().map(s -> new SqlQuery(s.id(), s.sql(), s.rowCount(), s.truncated())).toList(),
            i.toolExecutions().stream().map(t -> new ToolExecution(t.id(), t.toolName(), t.status(), t.startedAt(), t.completedAt(), t.durationMs())).toList(),
            i.createdAt(), i.completedAt(), i.error() == null ? null : new ErrorDetail(i.error().code(), i.error().message()), i.probableRootCause(), i.confidence());
    }
}
