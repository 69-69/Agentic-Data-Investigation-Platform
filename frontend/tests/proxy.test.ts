// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { forward } from "@/lib/proxy";
import result from "./fixtures/investigation.json";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
it("forwards only fixed Java paths and strips private response fields", async () => {
  vi.stubEnv("EXPERIENCE_API_BASE_URL", "http://localhost:8080");
  const fetcher = vi
    .fn()
    .mockResolvedValue(Response.json({ ...result, currentStep: "private" }));
  vi.stubGlobal("fetch", fetcher);
  const response = await forward(
    new NextRequest(
      "http://localhost/api/experience/investigations/" +
        result.investigationId,
    ),
    result.investigationId,
  );
  expect(response.status).toBe(200);
  expect(await response.json()).toEqual(result);
  expect(String(fetcher.mock.calls[0][0])).toBe(
    "http://localhost:8080/api/v1/investigations/" + result.investigationId,
  );
  expect(fetcher.mock.calls[0][1].redirect).toBe("error");
});
it("does not forward error bodies", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("password=secret", { status: 503 })),
  );
  const response = await forward(
    new NextRequest("http://localhost/x"),
    result.investigationId,
  );
  expect(response.status).toBe(503);
  expect(await response.text()).not.toContain("secret");
});
it("rejects caller-controlled path segments before fetching", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const response = await forward(
    new NextRequest("http://localhost/x"),
    "../../private",
  );
  expect(response.status).toBe(400);
  expect(fetcher).not.toHaveBeenCalled();
});
it("rejects configuration containing credentials", async () => {
  vi.stubEnv("EXPERIENCE_API_BASE_URL", "http://user:private@localhost");
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  expect(
    (
      await forward(
        new NextRequest("http://localhost/x"),
        result.investigationId,
      )
    ).status,
  ).toBe(503);
  expect(fetcher).not.toHaveBeenCalled();
});
it("rejects oversized request bodies before contacting Java", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const request = new NextRequest("http://localhost/x", {
    method: "POST",
    body: "x".repeat(16385),
  });
  expect((await forward(request)).status).toBe(413);
  expect(fetcher).not.toHaveBeenCalled();
});
it("rejects malformed successful responses", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({})));
  expect(
    (
      await forward(
        new NextRequest("http://localhost/x"),
        result.investigationId,
      )
    ).status,
  ).toBe(502);
});
