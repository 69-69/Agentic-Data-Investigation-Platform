import { Button } from "@mui/material";
import type { Investigation } from "@/lib/contracts";
import { percent } from "@/lib/format";
export default function FindingsPanel({
  findings,
  onEvidence,
}: {
  findings: Investigation["findings"];
  onEvidence: (id: string) => void;
}) {
  return (
    <section aria-labelledby="findings-heading">
      <div className="section-heading">
        <h2 id="findings-heading">Findings</h2>
        <span className="count-label">{findings.length} observations</span>
      </div>
      {!findings.length && (
        <p className="empty-copy">
          No supported findings were returned. Review the status and available
          evidence.
        </p>
      )}
      <div className="findings-list">
        {findings.map((f, i) => (
          <article className="finding" key={f.id}>
            <span className="finding-number">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div>
              <div className="finding-title">
                <h3>{f.title}</h3>
                <span>{percent(f.confidence)} confidence</span>
              </div>
              <p>{f.description}</p>
              <div className="evidence-links">
                {f.evidenceIds.map((id) => (
                  <Button
                    key={id}
                    size="small"
                    onClick={() => onEvidence(id)}
                    aria-label={`View evidence ${id}`}
                  >
                    {id} ↗
                  </Button>
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
