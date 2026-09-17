import { Chip } from "@mui/material";
import type { InvestigationStatusValue } from "@/lib/contracts";
const labels = {
  pending: "Pending",
  running: "Investigating",
  completed: "Completed",
  partial: "Partial result",
  failed: "Failed",
};
const colors = {
  pending: "default",
  running: "info",
  completed: "success",
  partial: "warning",
  failed: "error",
} as const;
export default function InvestigationStatus({
  status,
}: {
  status: InvestigationStatusValue;
}) {
  return (
    <Chip
      size="small"
      variant="outlined"
      label={labels[status]}
      color={colors[status]}
    />
  );
}
