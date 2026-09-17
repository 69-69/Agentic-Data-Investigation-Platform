"use client";
import { useState } from "react";
import { Button, Chip } from "@mui/material";
import type { Investigation } from "@/lib/contracts";
import { cell } from "@/lib/format";
function EvidenceItem({
  item,
  truncated,
}: {
  item: Investigation["evidence"][number];
  truncated: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const rows = expanded ? item.rows : item.rows.slice(0, 10);
  return (
    <article id={`evidence-${item.id}`} tabIndex={-1} className="evidence-card">
      <div className="section-heading">
        <div className="inline">
          <span className="record-id">{item.id}</span>
          <h3>SQL result</h3>
        </div>
        <Chip
          size="small"
          label={`${item.rowCount} returned rows`}
          variant="outlined"
        />
      </div>
      <p>{item.description}</p>
      <span className="quiet-label">
        Source query: {item.sqlQueryId}
        {truncated ? " · Result truncated by the service" : ""}
      </span>
      {item.rows.length ? (
        <>
          <div
            className="table-scroll"
            role="region"
            aria-label={`Evidence ${item.id} rows`}
            tabIndex={0}
          >
            <table>
              <caption className="sr-only">{item.description}</caption>
              <thead>
                <tr>
                  {item.columns.map((c, i) => (
                    <th key={i} scope="col">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((value, j) => (
                      <td key={j} title={cell(value)}>
                        {cell(value).slice(0, 1000)}
                        {cell(value).length > 1000 ? "…" : ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {item.rows.length > 10 && (
            <Button size="small" onClick={() => setExpanded(!expanded)}>
              {expanded
                ? "Show first 10 rows"
                : `Show all ${item.rows.length} returned rows`}
            </Button>
          )}
        </>
      ) : (
        <p className="empty-copy">The query returned no rows.</p>
      )}
    </article>
  );
}
export default function EvidencePanel({
  evidence,
  queries,
}: {
  evidence: Investigation["evidence"];
  queries: Investigation["sqlQueries"];
}) {
  return (
    <section aria-label="Query evidence">
      <p className="section-intro">
        Returned data behind each finding. Row counts describe the query result,
        not necessarily the underlying dataset.
      </p>
      {evidence.length ? (
        evidence.map((e) => (
          <EvidenceItem
            key={e.id}
            item={e}
            truncated={
              queries.find((q) => q.id === e.sqlQueryId)?.truncated ?? false
            }
          />
        ))
      ) : (
        <p className="empty-copy">No query evidence was collected.</p>
      )}
    </section>
  );
}
