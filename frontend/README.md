# MedRep AI Frontend

Minimal Next.js chat UI for asking questions against the MedRep AI backend.

## Prerequisites

- Node.js 18+
- Backend running locally (default `http://localhost:8000`)
- A Google Cloud OAuth 2.0 Web Client ID (for sign-in)

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
```

Edit `.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_GOOGLE_CLIENT_ID=
```

Set `NEXT_PUBLIC_GOOGLE_CLIENT_ID` to your Google OAuth Web Client ID. Leave it empty only while scaffolding; the app shows a clear configuration message until it is set.

### Google OAuth client (Identity Services)

1. Open [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials.
2. Create credentials → **OAuth client ID** → Application type **Web application**.
3. Under **Authorized JavaScript origins**, add the origins that serve this app, for example:
   - `http://localhost:3000` (local Next.js)
   - your deployed frontend origin when you have one
4. You do not need Authorized redirect URIs for the GIS button / ID token flow used here.
5. Copy the **Client ID** into `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in `.env.local`.
6. Restart `npm run dev` after changing env vars.

Do not commit real client secrets. This app only needs the public Web Client ID (`NEXT_PUBLIC_…`). The Google ID token stays in memory for the signed-in session; `lib/api.ts` sends it as `Authorization: Bearer` on chat requests via `getIdToken()`. The token is not logged.

## Run locally

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Unauthenticated users see the Google sign-in screen; after sign-in, the chat UI is available.

## Backend note

The UI calls `POST /chat` on the configured API base URL with `Authorization: Bearer <Google ID token>`. Start the FastAPI backend separately before asking questions. Backend verification of that token is #34.

## CORS

The backend must allow this app’s origin via `CORS_ALLOWED_ORIGINS` (see `backend/.env.example`). For local Next.js, set `CORS_ALLOWED_ORIGINS=http://localhost:3000` in `backend/.env` and restart FastAPI. This frontend does not work around CORS.

## Scripts

- `npm run dev` — local development server
- `npm run build` — production build
- `npm start` — serve the production build
- `npm run lint` — ESLint
