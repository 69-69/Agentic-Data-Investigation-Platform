package com.portfolio.investigation.adapter.agent;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;

/** Versioned internal REST DTOs, kept separate from Java domain and public DTOs. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AgentPayload(@NotNull UUID investigationId, @NotBlank String status,
        @NotBlank @Size(max=2000) String question, @Size(max=16000) String summary,
        @NotNull @Size(max=100) List<@NotNull @Valid Finding> findings,
        @NotNull @Size(max=100) List<@NotNull @Valid Evidence> evidence,
        @NotNull @Size(max=100) List<@NotNull @Valid SqlQuery> sqlQueries,
        @NotNull @Size(max=100) List<@NotNull @Valid ToolExecution> toolExecutions,
        @NotNull Instant createdAt, Instant completedAt, @Size(max=8000) String probableRootCause,
        @DecimalMin("0.0") @DecimalMax("1.0") Double confidence) {
    public AgentPayload(UUID investigationId, String status, String question, String summary,
        List<Finding> findings, List<Evidence> evidence, List<SqlQuery> sqlQueries,
        List<ToolExecution> toolExecutions, Instant createdAt, Instant completedAt) {
        this(investigationId, status, question, summary, findings, evidence, sqlQueries, toolExecutions, createdAt, completedAt, null, 0.0);
    }
    public record Create(String question) {}
    public record Finding(@NotBlank String id, @NotBlank String description,
                          @NotNull List<@NotBlank String> evidenceIds, @Size(max=160) String title,
                          @DecimalMin("0.0") @DecimalMax("1.0") Double confidence) {
        public Finding(String id, String description, List<String> evidenceIds) { this(id, description, evidenceIds, "Observation", 0.0); }
    }
    public record Evidence(@NotBlank String id, @NotBlank String description,
                           @NotBlank String sqlQueryId, @NotNull List<@NotBlank String> columns,
                           @NotNull @Size(max=500) List<@NotNull List<Object>> rows,
                           @Pattern(regexp="sql_result") String type, String query, @Min(0) @Max(500) Integer rowCount) {
        public Evidence(String id, String description, String sqlQueryId, List<String> columns, List<List<Object>> rows) {
            this(id, description, sqlQueryId, columns, rows, "sql_result", null, rows.size());
        }
    }
    public record SqlQuery(@NotBlank String id, @NotBlank String sql,
                           @NotNull @Min(0) @Max(500) Integer rowCount, @NotNull Boolean truncated) {}
    public record ToolExecution(@NotBlank String id, @NotBlank String toolName,
            @Pattern(regexp="completed|failed") @NotNull String status,
            @NotNull Instant startedAt, @NotNull Instant completedAt,
            @NotNull @Min(0) Long durationMs) {}
}
