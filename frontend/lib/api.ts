import { getIdToken } from "@/lib/auth";
import type { ChatRequest, ChatResponse, Citation } from "./types";

const CHAT_REQUEST_TIMEOUT_MS = 60_000;

const AUTH_ERROR_MESSAGE =
  "Your session expired or you are not signed in. Please sign in again.";
const TIMEOUT_ERROR_MESSAGE =
  "The request timed out. Please try again.";
const NETWORK_ERROR_MESSAGE =
  "Could not reach the server. Check your connection and try again.";

export class AuthError extends Error {
  constructor(message: string = AUTH_ERROR_MESSAGE) {
    super(message);
    this.name = "AuthError";
  }
}

function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!raw || !raw.trim()) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not set. Copy .env.example to .env.local and set the backend URL."
    );
  }
  return raw.trim().replace(/\/+$/, "");
}

/**
 * Attach Authorization: Bearer from getIdToken(). Never log the token.
 * Throws AuthError when no token is available (caller must not fetch).
 */
export function getAuthHeaders(): Record<string, string> {
  const token = getIdToken();
  if (!token) {
    throw new AuthError();
  }
  return { Authorization: `Bearer ${token}` };
}

function buildHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...getAuthHeaders(),
  };
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.error?.message === "string" && body.error.message.trim()) {
      return body.error.message;
    }
    if (typeof body?.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body?.detail)) {
      return body.detail
        .map((item: { msg?: string } | string) =>
          typeof item === "string" ? item : item.msg ?? JSON.stringify(item)
        )
        .join("; ");
    }
    if (typeof body?.message === "string") {
      return body.message;
    }
  } catch {
    // fall through
  }
  return `Request failed (${response.status} ${response.statusText})`;
}

function isAbortError(err: unknown): boolean {
  return (
    (err instanceof DOMException && err.name === "AbortError") ||
    (err instanceof Error && err.name === "AbortError")
  );
}

export async function askChat(question: string): Promise<ChatResponse> {
  const baseUrl = getApiBaseUrl();
  const payload: ChatRequest = { question };
  const headers = buildHeaders();

  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    CHAT_REQUEST_TIMEOUT_MS
  );

  try {
    let response: Response;
    try {
      response = await fetch(`${baseUrl}/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    } catch (err) {
      if (isAbortError(err)) {
        throw new Error(TIMEOUT_ERROR_MESSAGE);
      }
      throw new Error(NETWORK_ERROR_MESSAGE);
    }

    if (response.status === 401) {
      throw new AuthError();
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response));
    }

    const data = (await response.json()) as ChatResponse;
    const citations: Citation[] = data.citations ?? [];

    return {
      answer: data.answer,
      source: data.source ?? null,
      citations,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}
