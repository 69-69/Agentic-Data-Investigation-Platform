"use client";
import { Button, TextField } from "@mui/material";
import ArrowForwardRounded from "@mui/icons-material/ArrowForwardRounded";
import { useState } from "react";
export const examples = [
  ["Volume decline", "Why did transaction volume decline last week?"],
  ["Rejection spike", "What caused rejected records to spike?"],
  ["Duplicates", "Are there duplicate transactions in the recent period?"],
  [
    "Regional anomaly",
    "Which region experienced abnormal transaction behavior?",
  ],
  ["Deployment impact", "Did a deployment correlate with a pipeline incident?"],
];
export default function InvestigationForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (question: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || question.trim().length > 2000) {
      setError("Enter a question between 1 and 2,000 characters.");
      return;
    }
    setError("");
    onSubmit(question.trim());
  }
  return (
    <section className="question-card" aria-labelledby="question-title">
      <div className="section-heading">
        <span className="eyebrow">NEW INVESTIGATION</span>
        <span className="quiet-label">Read-only analysis</span>
      </div>
      <h2 id="question-title">What would you like to understand?</h2>
      <form onSubmit={submit}>
        <TextField
          label="Investigation question"
          placeholder="Why did transaction volume decline last week?"
          multiline
          minRows={2}
          maxRows={6}
          fullWidth
          value={question}
          disabled={busy}
          error={Boolean(error)}
          helperText={
            error || `${question.length.toLocaleString()} / 2,000 characters`
          }
          slotProps={{ htmlInput: { maxLength: 2000 } }}
          onChange={(e) => {
            setQuestion(e.target.value);
            setError("");
          }}
        />
        <div className="form-footer">
          <p>Ask a focused question. Follow the evidence.</p>
          <Button
            type="submit"
            variant="contained"
            disabled={busy}
            endIcon={<ArrowForwardRounded />}
            size="large"
          >
            {busy ? "Investigating…" : "Run investigation"}
          </Button>
        </div>
      </form>
      <div className="suggestions">
        <span>TRY A QUESTION</span>
        <div>
          {examples.map(([label, value]) => (
            <Button
              key={label}
              size="small"
              variant="outlined"
              disabled={busy}
              onClick={() => {
                setQuestion(value);
                setError("");
              }}
            >
              {label}
            </Button>
          ))}
        </div>
      </div>
    </section>
  );
}
