# MedRep AI Frontend

Minimal Next.js chat UI for MedRep AI.

## Stack

- Next.js App Router
- TypeScript
- Plain CSS

## Conventions

- Keep the UI minimal: one chat page with question, answer, error, and citations.
- Put UI pieces under `components/`, shared types and API client under `lib/`.
- Do not add a design system, auth, or frontend tests unless a GitHub issue requires it.
- Use `NEXT_PUBLIC_API_BASE_URL` for the backend base URL. Never commit secrets.
- Auth headers are stubbed in `lib/api.ts` (`getAuthHeaders`) for later work (#33/#35).
