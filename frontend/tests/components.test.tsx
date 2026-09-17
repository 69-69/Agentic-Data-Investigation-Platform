import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect, vi } from "vitest";
import InvestigationForm from "@/components/InvestigationForm";
import InvestigationResult from "@/components/InvestigationResult";
import ErrorState from "@/components/ErrorState";
import Dashboard from "@/components/Dashboard";
import { ApiError, api } from "@/lib/api";
import { resultSchema } from "@/lib/contracts";
import raw from "./fixtures/investigation.json";
const result = resultSchema.parse(raw);
it("validates the form and uses suggested questions without auto-submitting", async () => {
  const user = userEvent.setup();
  const submit = vi.fn();
  render(<InvestigationForm busy={false} onSubmit={submit} />);
  await user.click(screen.getByRole("button", { name: "Run investigation" }));
  expect(submit).not.toHaveBeenCalled();
  expect(
    screen.getByText("Enter a question between 1 and 2,000 characters."),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Duplicates" }));
  expect(submit).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Run investigation" }));
  expect(submit).toHaveBeenCalledWith(
    "Are there duplicate transactions in the recent period?",
  );
});
it("connects findings to evidence and exposes SQL on demand", async () => {
  const user = userEvent.setup();
  render(<InvestigationResult result={result} />);
  expect(screen.getByText(result.summary!)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "View evidence e1" }));
  expect(
    screen.getByRole("region", { name: "Evidence e1 rows" }),
  ).toBeVisible();
  expect(screen.getByRole("tab", { name: /Evidence/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await user.click(screen.getByRole("tab", { name: /SQL/ }));
  await user.click(screen.getAllByText("s1")[0]);
  expect(screen.getByRole("button", { name: "Copy query s1" })).toBeVisible();
});
it("labels partial results and unavailable root causes", () => {
  render(
    <InvestigationResult
      result={{ ...result, status: "partial", probableRootCause: null }}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("partial result");
  expect(
    screen.getByText("Insufficient evidence to establish a root cause."),
  ).toBeVisible();
});
it("renders safe errors with a request ID", () => {
  render(<ErrorState error={new ApiError("AGENT_UNAVAILABLE", "trace-id")} />);
  expect(screen.getByRole("alert")).toHaveTextContent("trace-id");
});
it("runs POST then GET and stores metadata only in session history", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "create").mockResolvedValue(result);
  vi.spyOn(api, "get").mockResolvedValue(result);
  render(<Dashboard />);
  await user.click(screen.getByRole("button", { name: "Volume decline" }));
  await user.click(screen.getByRole("button", { name: "Run investigation" }));
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: result.question }),
    ).toBeVisible(),
  );
  expect(api.create).toHaveBeenCalledTimes(1);
  expect(api.get).toHaveBeenCalledTimes(1);
  expect(
    screen.getByRole("navigation", { name: "Investigation history" }),
  ).toHaveTextContent(result.question);
  const saved = JSON.parse(
    sessionStorage.getItem("trace-investigation-history-v1")!,
  );
  expect(saved[0]).toEqual({
    investigationId: result.investigationId,
    question: result.question,
    status: result.status,
    createdAt: result.createdAt,
  });
});
it("keeps a created investigation available when GET fails", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "create").mockResolvedValue(result);
  vi.spyOn(api, "get").mockRejectedValue(new ApiError("AGENT_UNAVAILABLE"));
  render(<Dashboard />);
  await user.click(screen.getByRole("button", { name: "Volume decline" }));
  await user.click(screen.getByRole("button", { name: "Run investigation" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Retry lookup" })).toBeVisible(),
  );
  expect(
    screen.getByRole("navigation", { name: "Investigation history" }),
  ).toHaveTextContent(result.question);
  expect(api.create).toHaveBeenCalledTimes(1);
});

it("keeps tab controls connected to existing panels", () => {
  render(<InvestigationResult result={result} />);
  for (const tab of screen.getAllByRole("tab")) {
    expect(
      document.getElementById(tab.getAttribute("aria-controls")!),
    ).not.toBeNull();
  }
});
it("shows honest loading and supports stopping the wait", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "create").mockImplementation(
    (_question, signal) =>
      new Promise((_resolve, reject) => {
        signal?.addEventListener(
          "abort",
          () => reject(new ApiError("REQUEST_CANCELLED")),
          { once: true },
        );
      }),
  );
  render(<Dashboard />);
  await user.click(screen.getByRole("button", { name: "Volume decline" }));
  await user.click(screen.getByRole("button", { name: "Run investigation" }));
  expect(screen.getByRole("status")).toHaveTextContent("Waiting for evidence");
  expect(screen.getByRole("button", { name: "Investigating…" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Stop waiting" }));
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("Stopped waiting"),
  );
  expect(api.create).toHaveBeenCalledTimes(1);
});
it("loads history metadata after remount and retrieves the selected result", async () => {
  const user = userEvent.setup();
  sessionStorage.setItem(
    "trace-investigation-history-v1",
    JSON.stringify([
      {
        investigationId: result.investigationId,
        question: result.question,
        status: result.status,
        createdAt: result.createdAt,
      },
    ]),
  );
  vi.spyOn(api, "get").mockResolvedValue(result);
  const create = vi.spyOn(api, "create");
  render(<Dashboard />);
  await user.click(
    screen.getByRole("button", {
      name: new RegExp(result.question.replace(/\?/g, "\\?")),
    }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: result.question }),
    ).toBeVisible(),
  );
  expect(api.get).toHaveBeenCalledTimes(1);
  expect(create).not.toHaveBeenCalled();
});
