"use client";
import { useState } from "react";
import { Button, Chip } from "@mui/material";
import ContentCopyRounded from "@mui/icons-material/ContentCopyRounded";
import type { Investigation } from "@/lib/contracts";
export default function SqlEvidenceViewer({
  queries,
}: {
  queries: Investigation["sqlQueries"];
}) {
  const [notice, setNotice] = useState("");
  async function copy(sql: string, id: string) {
    try {
      await navigator.clipboard.writeText(sql);
      setNotice(`${id} copied to clipboard.`);
    } catch {
      setNotice(
        "Clipboard unavailable. Select and copy the SQL text manually.",
      );
    }
  }
  return (
    <section aria-label="Executed SQL">
      <p className="section-intro">
        The exact bounded SQL returned by the service. Expand a query to inspect
        or copy it.
      </p>
      <div role="status" className="quiet-label">
        {notice}
      </div>
      {queries.map((q) => (
        <details className="sql-card" key={q.id}>
          <summary>
            <span className="record-id">{q.id}</span>
            <span className="sql-preview">{q.sql}</span>
            <Chip
              size="small"
              variant="outlined"
              label={`${q.rowCount} rows${q.truncated ? " · truncated" : ""}`}
            />
          </summary>
          <div className="sql-toolbar">
            <span className="quiet-label">Read-only query evidence</span>
            <Button
              size="small"
              startIcon={<ContentCopyRounded />}
              onClick={() => void copy(q.sql, q.id)}
              aria-label={`Copy query ${q.id}`}
            >
              Copy SQL
            </Button>
          </div>
          <pre tabIndex={0} aria-label={`SQL query ${q.id}`}>
            <code>{q.sql}</code>
          </pre>
        </details>
      ))}
      {!queries.length && (
        <p className="empty-copy">No SQL queries were executed.</p>
      )}
    </section>
  );
}
