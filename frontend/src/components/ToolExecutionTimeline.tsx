import type { Investigation } from "@/lib/contracts";
import { timestamp } from "@/lib/format";
const names: Record<string, string> = {
  inspect_schema: "Inspect database schema",
  get_database_schema: "Inspect database schema",
  get_table_metadata: "Inspect table metadata",
  execute_readonly_sql: "Execute guarded SQL",
  execute_read_only_sql: "Execute guarded SQL",
  validate_sql: "Validate SQL",
};
export default function ToolExecutionTimeline({
  executions,
}: {
  executions: Investigation["toolExecutions"];
}) {
  return (
    <section aria-label="Tool execution timeline">
      <p className="section-intro">
        Recorded tool activity. This is an execution trace, not the model’s
        private reasoning.
      </p>
      <ol className="timeline">
        {executions.map((t) => (
          <li key={t.id} className={t.status === "failed" ? "failed" : ""}>
            <span className="timeline-dot" aria-hidden="true" />
            <div>
              <div className="section-heading">
                <h3>{names[t.toolName] || t.toolName.replaceAll("_", " ")}</h3>
                <span className="count-label">
                  {t.durationMs.toLocaleString()} ms
                </span>
              </div>
              <p>
                <span className={`tool-outcome ${t.status}`}>
                  {t.status === "completed" ? "Completed" : "Failed"}
                </span>{" "}
                · <time dateTime={t.startedAt}>{timestamp(t.startedAt)}</time>
              </p>
              <span className="quiet-label">
                Finished{" "}
                <time dateTime={t.completedAt}>{timestamp(t.completedAt)}</time>
              </span>
            </div>
          </li>
        ))}
      </ol>
      {!executions.length && (
        <p className="empty-copy">No tool executions were recorded.</p>
      )}
    </section>
  );
}
