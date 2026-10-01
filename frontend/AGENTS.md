# MedRep AI Frontend

Minimal Next.js chat UI for MedRep AI.

## Stack

- Next.js App Router
- TypeScript
- Plain CSS
- Google Identity Services (GIS) for Google ID token sign-in (#33)

## Conventions

- Keep the UI minimal: one chat page with question, answer, error, and citations.
- Put UI pieces under `components/`, shared types and API client under `lib/`.
- Do not add a design system or frontend tests unless a GitHub issue requires it.
- Auth (#33): GIS via `https://accounts.google.com/gsi/client`; configure with `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Token lives in React memory only; use `getIdToken()` / `useAuth()` from `lib/auth.tsx`. Do not log tokens.
- Use `NEXT_PUBLIC_API_BASE_URL` for the backend base URL. Never commit secrets.
- Auth headers: `lib/api.ts` (`getAuthHeaders` / `askChat`) attaches `Authorization: Bearer` from `getIdToken()`, uses a request timeout, and treats missing token / 401 as auth failure (never log the token).
