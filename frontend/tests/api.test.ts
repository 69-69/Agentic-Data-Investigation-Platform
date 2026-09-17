import { describe, it, expect, vi } from "vitest";
import { createApiClient } from "@/lib/api";
import fixture from "./fixtures/investigation.json";
const created = {
  investigationId: fixture.investigationId,
  status: fixture.status,
  question: fixture.question,
  createdAt: fixture.createdAt,
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
describe("typed API boundary", () => {
  it("trims input, propagates a UUID and never retries POST", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(created, 201));
    const client = createApiClient("/api/experience", fetcher);
    expect(await client.create("  " + fixture.question + "  ")).toEqual(
      created,
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("/api/experience/investigations");
    expect(JSON.parse(options.body)).toEqual({ question: fixture.question });
    expect(options.headers["X-Correlation-Id"]).toMatch(/^[a-f0-9-]{36}$/);
  });
  it("rejects blank questions without a request", async () => {
    const fetcher = vi.fn();
    await expect(
      createApiClient("", fetcher).create("  "),
    ).rejects.toMatchObject({ code: "INVALID_REQUEST" });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("validates full results", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(fixture));
    expect(
      await createApiClient("", fetcher).get(fixture.investigationId),
    ).toEqual(fixture);
  });
  it.each([
    {},
    { ...fixture, confidence: 3 },
    { ...fixture, status: "invented" },
  ])("rejects malformed success payload", async (body) => {
    const fetcher = vi.fn().mockResolvedValue(response(body));
    await expect(
      createApiClient("", fetcher).get(fixture.investigationId),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
  it("does not expose raw downstream messages", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        response(
          { error: { code: "AGENT_UNAVAILABLE", message: "password=private" } },
          503,
        ),
      );
    await expect(
      createApiClient("", fetcher).create(fixture.question),
    ).rejects.toMatchObject({ code: "AGENT_UNAVAILABLE" });
    try {
      await createApiClient("", fetcher).create(fixture.question);
    } catch (e) {
      expect(String(e)).not.toContain("private");
    }
  });
  it("rejects mismatched IDs", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(fixture));
    await expect(
      createApiClient("", fetcher).get("00000000-0000-4000-8000-000000000001"),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
  it("normalizes connection failures", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("secret host"));
    await expect(
      createApiClient("", fetcher).get(fixture.investigationId),
    ).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });
  it("bounds requests with a deadline", async () => {
    const fetcher = vi.fn(
      (_url, options) =>
        new Promise<Response>((_resolve, reject) =>
          options?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          ),
        ),
    );
    await expect(
      createApiClient("", fetcher, 5).create(fixture.question),
    ).rejects.toMatchObject({ code: "AGENT_TIMEOUT" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("distinguishes user cancellation", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn(
      (_url, options) =>
        new Promise<Response>((_resolve, reject) =>
          options?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          ),
        ),
    );
    const promise = createApiClient("", fetcher).get(
      fixture.investigationId,
      controller.signal,
    );
    controller.abort();
    await expect(promise).rejects.toMatchObject({ code: "REQUEST_CANCELLED" });
  });
});
