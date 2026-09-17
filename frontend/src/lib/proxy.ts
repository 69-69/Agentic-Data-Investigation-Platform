import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "node:crypto";
import { createdSchema, resultSchema } from "./contracts";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
async function readBounded(
  stream: ReadableStream<Uint8Array> | null,
  maximum: number,
) {
  const reader = stream?.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  if (reader) {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > maximum) {
        await reader.cancel();
        throw new Error("BODY_LIMIT");
      }
      chunks.push(value);
    }
  }
  return Buffer.concat(chunks).toString("utf8");
}
export async function forward(request: NextRequest, id?: string) {
  const input = request.headers.get("X-Correlation-Id") ?? "";
  const correlationId = uuid.test(input) ? input.toLowerCase() : randomUUID();
  const headers = {
    "X-Correlation-Id": correlationId,
    "Cache-Control": "no-store",
  };
  const error = (status: number, code: string) =>
    NextResponse.json(
      {
        error: { code, message: "The request could not be completed." },
        correlationId,
      },
      { status, headers },
    );
  if (id !== undefined && !uuid.test(id)) return error(400, "INVALID_REQUEST");
  let origin: URL;
  try {
    origin = new URL(
      process.env.EXPERIENCE_API_BASE_URL || "http://127.0.0.1:8080",
    );
    if (
      !["http:", "https:"].includes(origin.protocol) ||
      origin.username ||
      origin.password ||
      origin.search ||
      origin.hash ||
      origin.pathname !== "/"
    )
      throw new Error();
  } catch {
    return error(503, "AGENT_UNAVAILABLE");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 67000);
  try {
    let body: string | undefined;
    if (request.method === "POST") {
      try {
        body = await readBounded(request.body, 16384);
      } catch {
        return error(413, "INVALID_REQUEST");
      }
    }
    // Fixed paths/origin and no forwarded credentials: never an open proxy.
    const response = await fetch(
      new URL("/api/v1/investigations" + (id ? "/" + id : ""), origin),
      {
        method: request.method,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-Correlation-Id": correlationId,
        },
        body,
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      },
    );
    if (!response.ok) {
      await response.body?.cancel();
      const codes: Record<number, string> = {
        400: "INVALID_REQUEST",
        404: "INVESTIGATION_NOT_FOUND",
        405: "HTTP_405",
        415: "HTTP_415",
        500: "INTERNAL_ERROR",
        502: "AGENT_BAD_RESPONSE",
        503: "AGENT_UNAVAILABLE",
        504: "AGENT_TIMEOUT",
      };
      return error(
        codes[response.status] ? response.status : 502,
        codes[response.status] || "AGENT_BAD_RESPONSE",
      );
    }
    let data: unknown;
    try {
      data = JSON.parse(await readBounded(response.body, 1024 * 1024));
    } catch {
      return error(
        controller.signal.aborted ? 504 : 502,
        controller.signal.aborted ? "AGENT_TIMEOUT" : "AGENT_BAD_RESPONSE",
      );
    }
    const parsed = (id ? resultSchema : createdSchema).safeParse(data);
    if (!parsed.success || (id && parsed.data.investigationId !== id))
      return error(502, "AGENT_BAD_RESPONSE");
    return NextResponse.json(parsed.data, { status: response.status, headers });
  } catch {
    return error(
      controller.signal.aborted ? 504 : 503,
      controller.signal.aborted ? "AGENT_TIMEOUT" : "AGENT_UNAVAILABLE",
    );
  } finally {
    clearTimeout(timer);
  }
}
