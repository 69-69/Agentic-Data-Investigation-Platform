package com.portfolio.investigation.domain;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record Investigation(UUID id, Status status, String question, String summary,
        List<Finding> findings, List<Evidence> evidence, List<SqlQuery> sqlQueries,
        List<ToolExecution> toolExecutions, Instant createdAt, Instant completedAt,
        Failure error, String probableRootCause, double confidence) {
    public Investigation(UUID id, Status status, String question, String summary,
        List<Finding> findings, List<Evidence> evidence, List<SqlQuery> sqlQueries,
        List<ToolExecution> toolExecutions, Instant createdAt, Instant completedAt, Failure error) {
        this(id, status, question, summary, findings, evidence, sqlQueries, toolExecutions, createdAt, completedAt, error, null, 0.0);
    }
    public enum Status { PENDING, RUNNING, COMPLETED, PARTIAL, FAILED }
    public record Finding(String id, String description, List<String> evidenceIds, String title, double confidence) {
        public Finding(String id, String description, List<String> evidenceIds) { this(id, description, evidenceIds, "Observation", 0.0); }
    }
    public record Evidence(String id, String description, String sqlQueryId,
                           List<String> columns, List<List<Object>> rows, String type, String query, int rowCount) {
        public Evidence(String id, String description, String sqlQueryId, List<String> columns, List<List<Object>> rows) {
            this(id, description, sqlQueryId, columns, rows, "sql_result", "", rows.size());
        }
    }
    public record SqlQuery(String id, String sql, int rowCount, boolean truncated) {}
    public record ToolExecution(String id, String toolName, String status, Instant startedAt,
                                Instant completedAt, long durationMs) {}
    public record Failure(String code, String message) {}
}
