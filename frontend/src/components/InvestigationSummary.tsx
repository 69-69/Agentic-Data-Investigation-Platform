import { LinearProgress } from "@mui/material";
import type { Investigation } from "@/lib/contracts";
import { percent } from "@/lib/format";
export default function InvestigationSummary({
  result,
}: {
  result: Investigation;
}) {
  return (
    <section className="summary-grid" aria-label="Investigation summary">
      <div className="summary-body">
        <span className="eyebrow">EXECUTIVE SUMMARY</span>
        <p className="summary-text">
          {result.summary || "No summary is available for this investigation."}
        </p>
        <div className="cause">
          <span className="eyebrow">PROBABLE ROOT CAUSE</span>
          <p>
            {result.probableRootCause ||
              "Insufficient evidence to establish a root cause."}
          </p>
        </div>
      </div>
      <aside className="confidence">
        <span className="eyebrow">CONFIDENCE</span>
        <strong>{percent(result.confidence)}</strong>
        <LinearProgress
          variant="determinate"
          value={result.confidence * 100}
          aria-label="Overall confidence"
        />
        <p>
          Agent assessment, not a statistical probability. Correlation does not
          prove causation.
        </p>
      </aside>
    </section>
  );
}
