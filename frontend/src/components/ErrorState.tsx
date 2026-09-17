import { Alert, AlertTitle, Button } from "@mui/material";
import { ApiError } from "@/lib/api";
export default function ErrorState({
  error,
  onRetry,
}: {
  error: ApiError;
  onRetry?: () => void;
}) {
  return (
    <Alert
      severity={error.code === "REQUEST_CANCELLED" ? "info" : "error"}
      className="error-state"
      role="alert"
      action={
        onRetry ? (
          <Button color="inherit" onClick={onRetry}>
            Retry lookup
          </Button>
        ) : undefined
      }
    >
      <AlertTitle>
        {error.code === "REQUEST_CANCELLED"
          ? "Stopped waiting"
          : "Investigation unavailable"}
      </AlertTitle>
      {error.message}
      {error.correlationId && (
        <div className="trace-id">Request ID: {error.correlationId}</div>
      )}
    </Alert>
  );
}
