import type { ChatRequest, ChatResponse, Citation } from "./types";

function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!raw || !raw.trim()) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not set. Copy .env.example to .env.local and set the backend URL."
    );
  }
  return raw.trim().replace(/\/+$/, "");
}

/** Stub for future auth (#33/#35). Returns no auth headers yet. */
export function getAuthHeaders(): Record<string, string> {
  return {};
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

export async function askChat(question: string): Promise<ChatResponse> {
  const baseUrl = getApiBaseUrl();
  const payload: ChatRequest = { question };

  const response = await fetch(`${baseUrl}/chat`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });

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
}
