import { z } from "zod";
export const statusSchema = z.enum([
  "pending",
  "running",
  "completed",
  "partial",
  "failed",
]);
const timestamp = z.string().datetime({ offset: true });
const confidence = z.number().min(0).max(1);
export const createdSchema = z.object({
  investigationId: z.string().uuid(),
  status: statusSchema,
  question: z.string().max(2000),
  createdAt: timestamp,
});
export const resultSchema = createdSchema.extend({
  summary: z.string().max(16000).nullable(),
  probableRootCause: z.string().max(8000).nullable(),
  confidence,
  completedAt: timestamp.nullable(),
  error: z.object({ code: z.string(), message: z.string() }).nullable(),
  findings: z
    .array(
      z.object({
        id: z.string(),
        title: z.string(),
        description: z.string(),
        confidence,
        evidenceIds: z.array(z.string()),
      }),
    )
    .max(100),
  evidence: z
    .array(
      z.object({
        id: z.string(),
        type: z.literal("sql_result"),
        description: z.string(),
        query: z.string(),
        rowCount: z.number().int().min(0).max(500),
        sqlQueryId: z.string(),
        columns: z.array(z.string()),
        rows: z.array(z.array(z.unknown())).max(500),
      }),
    )
    .max(100),
  sqlQueries: z
    .array(
      z.object({
        id: z.string(),
        sql: z.string(),
        rowCount: z.number().int().min(0).max(500),
        truncated: z.boolean(),
      }),
    )
    .max(100),
  toolExecutions: z
    .array(
      z.object({
        id: z.string(),
        toolName: z.string(),
        status: z.enum(["completed", "failed"]),
        startedAt: timestamp,
        completedAt: timestamp,
        durationMs: z.number().min(0),
      }),
    )
    .max(100),
});
export type Investigation = z.infer<typeof resultSchema>;
export type HistoryItem = z.infer<typeof createdSchema>;
export type InvestigationStatusValue = z.infer<typeof statusSchema>;
export const historySchema = z.array(createdSchema).max(20);
