import { z } from "zod";
import { createdSchema, resultSchema } from "./contracts";
const messages: Record<string, string> = {
  AGENT_UNAVAILABLE:
    "The investigation service is unavailable. Check that Java and Python are running.",
  AGENT_TIMEOUT:
    "The investigation timed out. It may still have run on the server; submitting again creates a new investigation.",
  AGENT_BAD_RESPONSE: "The investigation service returned an invalid response.",
  INVESTIGATION_NOT_FOUND:
    "This investigation is no longer available. Results expire and are lost when the agent restarts.",
  INVALID_REQUEST: "Enter a question between 1 and 2,000 characters.",
  REQUEST_CANCELLED:
    "You stopped waiting. Server work may continue; submitting again creates a new investigation.",
  NETWORK_ERROR:
    "Could not reach the API. Check your connection and local services.",
  INVALID_RESPONSE:
    "The API response did not match the investigation contract.",
  POLLING_TIMEOUT:
    "The investigation is still active. Select it in history to check again.",
};
export class ApiError extends Error {
  constructor(
    public code: string,
    public correlationId?: string,
  ) {
    super(
      messages[code] ??
        "The request could not be completed. Please check the services and try again.",
    );
    this.name = "ApiError";
  }
}
export function createApiClient(
  base = process.env.NEXT_PUBLIC_EXPERIENCE_API_BASE_URL || "/api/experience",
  fetcher: typeof fetch = (...args) => fetch(...args),
  timeoutMs = 70000,
) {
  const root = base.replace(/\/$/, "");
  async function request<T>(
    path: string,
    schema: z.ZodType<T>,
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<T> {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) abort();
    let expired = false;
    const timer = setTimeout(() => {
      expired = true;
      controller.abort();
    }, timeoutMs);
    const trace = crypto.randomUUID();
    try {
      const response = await fetcher(root + path, {
        method: body ? "POST" : "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Correlation-Id": trace,
        },
        body: body ? JSON.stringify(body) : undefined,
        cache: "no-store",
        signal: controller.signal,
      });
      const correlation = z
        .string()
        .uuid()
        .safeParse(response.headers.get("X-Correlation-Id"));
      const id = correlation.success ? correlation.data : trace;
      let data: unknown;
      try {
        data = await response.json();
      } catch {
        throw new ApiError("INVALID_RESPONSE", id);
      }
      if (!response.ok) {
        const error = z
          .object({ error: z.object({ code: z.string() }) })
          .safeParse(data);
        throw new ApiError(
          error.success ? error.data.error.code : "INVALID_RESPONSE",
          id,
        );
      }
      const result = schema.safeParse(data);
      if (!result.success) throw new ApiError("INVALID_RESPONSE", id);
      return result.data;
    } catch (error) {
      if (expired) throw new ApiError("AGENT_TIMEOUT", trace);
      if (signal?.aborted) throw new ApiError("REQUEST_CANCELLED", trace);
      if (error instanceof ApiError) throw error;
      throw new ApiError("NETWORK_ERROR", trace);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
    }
  }
  return {
    async create(question: string, signal?: AbortSignal) {
      const normalized = question.trim();
      if (!normalized || normalized.length > 2000)
        throw new ApiError("INVALID_REQUEST");
      const result = await request(
        "/investigations",
        createdSchema,
        { question: normalized },
        signal,
      );
      if (result.question !== normalized)
        throw new ApiError("INVALID_RESPONSE");
      return result;
    },
    async get(id: string, signal?: AbortSignal) {
      if (!z.string().uuid().safeParse(id).success)
        throw new ApiError("INVALID_REQUEST");
      const result = await request(
        "/investigations/" + encodeURIComponent(id),
        resultSchema,
        undefined,
        signal,
      );
      if (result.investigationId !== id) throw new ApiError("INVALID_RESPONSE");
      return result;
    },
  };
}
export const api = createApiClient();
