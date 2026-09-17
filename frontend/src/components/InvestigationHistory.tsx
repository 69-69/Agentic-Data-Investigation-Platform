import { Button } from "@mui/material";
import HistoryRounded from "@mui/icons-material/HistoryRounded";
import AddRounded from "@mui/icons-material/AddRounded";
import type { HistoryItem } from "@/lib/contracts";
import InvestigationStatus from "./InvestigationStatus";
import { timestamp } from "@/lib/format";
export default function InvestigationHistory({
  items,
  selected,
  busy,
  onSelect,
  onNew,
}: {
  items: HistoryItem[];
  selected?: string;
  busy: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <aside className="history-sidebar" aria-labelledby="history-heading">
      <Button
        variant="outlined"
        fullWidth
        startIcon={<AddRounded />}
        disabled={busy}
        onClick={onNew}
      >
        New investigation
      </Button>
      <div className="history-label">
        <HistoryRounded fontSize="small" />
        <h2 id="history-heading">Session history</h2>
        <span>{items.length}</span>
      </div>
      <nav aria-label="Investigation history">
        {items.length ? (
          <ol>
            {items.map((item) => (
              <li key={item.investigationId}>
                <button
                  disabled={busy}
                  className={`history-item ${selected === item.investigationId ? "selected" : ""}`}
                  aria-current={
                    selected === item.investigationId ? "true" : undefined
                  }
                  onClick={() => onSelect(item.investigationId)}
                >
                  <span className="history-question">{item.question}</span>
                  <time dateTime={item.createdAt}>
                    {timestamp(item.createdAt)}
                  </time>
                  <InvestigationStatus status={item.status} />
                </button>
              </li>
            ))}
          </ol>
        ) : (
          <div className="history-empty">
            <p>No investigations yet</p>
            <span>Your investigations will appear here as you explore.</span>
          </div>
        )}
      </nav>
      <div className="history-note">
        <span className="eyebrow">YOUR WORKSPACE</span>
        <p>
          History stays in this browser tab. Results depend on the service’s
          retention window.
        </p>
      </div>
    </aside>
  );
}
