"use client";
import { useEffect, useRef, useState } from "react";
import { Chip } from "@mui/material";
import HubRounded from "@mui/icons-material/HubRounded";
import ManageSearchRounded from "@mui/icons-material/ManageSearchRounded";
import AccountTreeOutlined from "@mui/icons-material/AccountTreeOutlined";
import DataObjectRounded from "@mui/icons-material/DataObjectRounded";
import FactCheckOutlined from "@mui/icons-material/FactCheckOutlined";
import { api, ApiError } from "@/lib/api";
import {
  historySchema,
  type HistoryItem,
  type Investigation,
} from "@/lib/contracts";
import InvestigationForm from "./InvestigationForm";
import InvestigationHistory from "./InvestigationHistory";
import InvestigationResult from "./InvestigationResult";
import LoadingState from "./LoadingState";
import ErrorState from "./ErrorState";
const storageKey = "trace-investigation-history-v1";
export default function Dashboard() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [result, setResult] = useState<Investigation>();
  const [selected, setSelected] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError>();
  const [formKey, setFormKey] = useState(0);
  const controller = useRef<AbortController | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    try {
      const saved = historySchema.safeParse(
        JSON.parse(sessionStorage.getItem(storageKey) || "[]"),
      );
      if (saved.success) setHistory(saved.data);
    } catch {}
    setHydrated(true);
    return () => {
      alive.current = false;
      controller.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (hydrated)
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(history));
      } catch {}
  }, [history, hydrated]);
  function remember(item: HistoryItem) {
    const { investigationId, status, question, createdAt } = item;
    setHistory((old) =>
      [
        { investigationId, status, question, createdAt },
        ...old.filter((x) => x.investigationId !== investigationId),
      ].slice(0, 20),
    );
  }
  async function run(question?: string, id?: string) {
    if (controller.current) return;
    const active = new AbortController();
    controller.current = active;
    setBusy(true);
    setError(undefined);
    setResult(undefined);
    setSelected(id);
    try {
      if (question) {
        const created = await api.create(question, active.signal);
        if (!alive.current) return;
        remember(created);
        id = created.investigationId;
        setSelected(id);
      }
      if (!id) return;
      const deadline = Date.now() + 180000;
      while (true) {
        const next = await api.get(id, active.signal);
        if (!alive.current) return;
        remember(next);
        if (next.status !== "pending" && next.status !== "running") {
          setResult(next);
          break;
        }
        if (Date.now() >= deadline) throw new ApiError("POLLING_TIMEOUT");
        await new Promise<void>((resolve, reject) => {
          const abort = () => {
            clearTimeout(timer);
            reject(new ApiError("REQUEST_CANCELLED"));
          };
          const timer = setTimeout(() => {
            active.signal.removeEventListener("abort", abort);
            resolve();
          }, 2000);
          if (active.signal.aborted) abort();
          else active.signal.addEventListener("abort", abort, { once: true });
        });
      }
    } catch (e) {
      if (alive.current)
        setError(e instanceof ApiError ? e : new ApiError("NETWORK_ERROR"));
    } finally {
      controller.current = null;
      if (alive.current) setBusy(false);
    }
  }
  useEffect(() => {
    if (result)
      document.getElementById("result-title")?.focus({ preventScroll: true });
  }, [result]);
  function fresh() {
    setResult(undefined);
    setSelected(undefined);
    setError(undefined);
    setFormKey((k) => k + 1);
    document.getElementById("main-content")?.focus();
  }
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to investigation
      </a>
      <header className="topbar">
        <a href="/" className="brand" aria-label="Trace home">
          <span className="brand-symbol">
            <HubRounded />
          </span>
          <span>
            trace<span className="brand-dot">.</span>
          </span>
          <span className="brand-divider" />
          <span className="brand-description">DATA INVESTIGATION</span>
        </a>
        <div className="topbar-right">
          <span className="quiet-label">Evidence-first workspace</span>
          <Chip label="Portfolio edition" size="small" variant="outlined" />
        </div>
      </header>
      <div className="app-shell">
        <InvestigationHistory
          items={history}
          selected={selected}
          busy={busy}
          onSelect={(id) => void run(undefined, id)}
          onNew={fresh}
        />
        <main id="main-content" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <span className="eyebrow">INVESTIGATION WORKSPACE</span>
              <h1>Turn questions into evidence.</h1>
              <p>
                Explore anomalies, follow the SQL, and understand what the data
                supports.
              </p>
            </div>
            <div className="workspace-badge">
              <ManageSearchRounded />
            </div>
          </div>
          <InvestigationForm
            key={formKey}
            busy={busy}
            onSubmit={(question) => void run(question)}
          />
          {error && (
            <ErrorState
              error={error}
              onRetry={
                selected ? () => void run(undefined, selected) : undefined
              }
            />
          )}
          {busy && (
            <LoadingState onCancel={() => controller.current?.abort()} />
          )}
          {result && !busy && (
            <InvestigationResult key={result.investigationId} result={result} />
          )}
          {!result && !busy && !error && (
            <section className="empty-state" aria-labelledby="empty-title">
              <div className="empty-icon">
                <AccountTreeOutlined />
              </div>
              <span className="eyebrow">FROM QUESTION TO UNDERSTANDING</span>
              <h2 id="empty-title">Every finding needs a paper trail.</h2>
              <p>
                Start an investigation to see the findings, supporting data,
                <br className="desktop-break" /> and the queries that connect
                them.
              </p>
              <div className="process-cards">
                {[
                  [
                    <ManageSearchRounded key="a" />,
                    "01",
                    "Ask a question",
                    "Focus on a change, anomaly, or incident.",
                  ],
                  [
                    <DataObjectRounded key="b" />,
                    "02",
                    "Inspect the evidence",
                    "Review read-only queries and returned data.",
                  ],
                  [
                    <FactCheckOutlined key="c" />,
                    "03",
                    "Assess the findings",
                    "Separate observations from possible causes.",
                  ],
                ].map(([icon, n, title, body], i) => (
                  <div key={i}>
                    <div className="process-top">
                      {icon}
                      <span>{n}</span>
                    </div>
                    <h3>{title}</h3>
                    <p>{body}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
          <footer className="workspace-footer">
            <span>Agentic Data Investigation Platform</span>
            <span>Traceable findings. Explicit uncertainty.</span>
          </footer>
        </main>
      </div>
    </>
  );
}
