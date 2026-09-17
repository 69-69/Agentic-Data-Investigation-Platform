package com.portfolio.investigation;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import com.portfolio.investigation.domain.Investigation;

public final class Fixtures {
    public static final UUID ID = UUID.fromString("11db2b38-a18a-42da-a32b-1f192d66caa1");
    public static final String QUESTION = "Why did volume decline?";
    public static String json() {
        return """
        {"investigationId":"11db2b38-a18a-42da-a32b-1f192d66caa1","status":"completed",
         "question":"Why did volume decline?","summary":"Observed a synthetic decline.",
         "findings":[{"id":"f1","description":"Volume declined","evidenceIds":["e1"]}],
         "evidence":[{"id":"e1","description":"Weekly count","sqlQueryId":"s1","columns":["count"],"rows":[[700]]}],
         "sqlQueries":[{"id":"s1","sql":"SELECT count(*) FROM analytics.transactions","rowCount":1,"truncated":false}],
         "toolExecutions":[{"id":"t1","toolName":"execute_readonly_sql","status":"completed",
           "startedAt":"2026-06-22T01:00:00Z","completedAt":"2026-06-22T01:00:01Z","durationMs":1000}],
         "createdAt":"2026-06-22T01:00:00Z","completedAt":"2026-06-22T01:00:02Z"}
        """;
    }
    public static Investigation result() {
        return new Investigation(ID, Investigation.Status.COMPLETED, QUESTION, "summary", List.of(), List.of(),
            List.of(), List.of(), Instant.parse("2026-06-22T01:00:00Z"), Instant.parse("2026-06-22T01:00:02Z"), null);
    }
}
