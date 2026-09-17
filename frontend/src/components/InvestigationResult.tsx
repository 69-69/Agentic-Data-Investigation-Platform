"use client";
import { useEffect, useState } from "react";
import { Alert, Tab, Tabs } from "@mui/material";
import type { Investigation } from "@/lib/contracts";
import { timestamp } from "@/lib/format";
import InvestigationStatus from "./InvestigationStatus";
import InvestigationSummary from "./InvestigationSummary";
import FindingsPanel from "./FindingsPanel";
import EvidencePanel from "./EvidencePanel";
import SqlEvidenceViewer from "./SqlEvidenceViewer";
import ToolExecutionTimeline from "./ToolExecutionTimeline";
export default function InvestigationResult({
  result,
}: {
  result: Investigation;
}) {
  const [tab, setTab] = useState(0);
  const [target, setTarget] = useState<string>();
  useEffect(() => {
    if (tab === 1 && target) {
      const element = document.getElementById(`evidence-${target}`);
      element?.scrollIntoView?.({ block: "center", behavior: "smooth" });
      element?.focus({ preventScroll: true });
    }
  }, [tab, target]);
  const panels = [
    <>
      <InvestigationSummary key="summary" result={result} />
      <FindingsPanel
        key="findings"
        findings={result.findings}
        onEvidence={(id) => {
          setTarget(id);
          setTab(1);
        }}
      />
    </>,
    <EvidencePanel
      key="evidence"
      evidence={result.evidence}
      queries={result.sqlQueries}
    />,
    <SqlEvidenceViewer key="sql" queries={result.sqlQueries} />,
    <ToolExecutionTimeline key="timeline" executions={result.toolExecutions} />,
  ];
  return (
    <section className="result-card" aria-labelledby="result-title">
      <div className="result-header">
        <div className="section-heading">
          <span className="eyebrow">INVESTIGATION RESULT</span>
          <InvestigationStatus status={result.status} />
        </div>
        <h2 id="result-title" tabIndex={-1}>
          {result.question}
        </h2>
        <div className="result-meta">
          <span>
            Started{" "}
            <time dateTime={result.createdAt}>
              {timestamp(result.createdAt)}
            </time>
          </span>
          {result.completedAt && (
            <span>
              Completed{" "}
              <time dateTime={result.completedAt}>
                {timestamp(result.completedAt)}
              </time>
            </span>
          )}
        </div>
        <span className="trace-id">ID {result.investigationId}</span>
      </div>
      {result.status === "partial" && (
        <Alert severity="warning">
          This is a partial result. Some evidence or analysis could not be
          completed.
        </Alert>
      )}
      {result.status === "failed" && (
        <Alert severity="error">
          The investigation could not establish a supported result. Review the
          available evidence before starting a new request.
        </Alert>
      )}
      <Tabs
        value={tab}
        onChange={(_, value: number) => setTab(value)}
        variant="scrollable"
        scrollButtons="auto"
        aria-label="Investigation result sections"
      >
        {[
          "Overview",
          `Evidence (${result.evidence.length})`,
          `SQL (${result.sqlQueries.length})`,
          `Activity (${result.toolExecutions.length})`,
        ].map((label, i) => (
          <Tab
            key={i}
            label={label}
            id={`result-tab-${i}`}
            aria-controls={`result-panel-${i}`}
          />
        ))}
      </Tabs>
      {panels.map((panel, index) => (
        <div
          key={index}
          className="result-panel"
          role="tabpanel"
          hidden={tab !== index}
          id={`result-panel-${index}`}
          aria-labelledby={`result-tab-${index}`}
        >
          {tab === index ? panel : null}
        </div>
      ))}
    </section>
  );
}
