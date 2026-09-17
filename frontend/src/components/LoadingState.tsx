"use client";
import { Button, LinearProgress } from "@mui/material";
import { useEffect, useState } from "react";
export default function LoadingState({ onCancel }: { onCancel: () => void }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <section className="loading-card" aria-busy="true">
      <div className="section-heading">
        <div>
          <span className="eyebrow">INVESTIGATION IN PROGRESS</span>
          <h2 role="status">Waiting for evidence</h2>
        </div>
        <span className="elapsed">{seconds}s</span>
      </div>
      <LinearProgress aria-label="Investigation progress" />
      <p>
        The service is processing your request. Most local investigations finish
        quickly; model-backed runs can take about a minute.
      </p>
      <Button size="small" onClick={onCancel}>
        Stop waiting
      </Button>
      <span className="quiet-label">
        {" "}
        This does not cancel work on the server.
      </span>
    </section>
  );
}
