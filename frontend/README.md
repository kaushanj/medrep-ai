# MedRep AI Frontend

Minimal Next.js chat UI for asking questions against the MedRep AI backend.

## Prerequisites

- Node.js 18+
- Backend running locally (default `http://localhost:8000`)

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
```

Edit `.env.local` if your backend URL differs:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Run locally

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Backend note

The UI calls `POST /chat` on the configured API base URL. Start the FastAPI backend separately before asking questions.

## CORS limitation

Browser requests from the Next.js origin (e.g. `http://localhost:3000`) to the backend may be blocked by CORS until the backend is configured to allow the frontend origin. This frontend does not work around CORS. If requests fail in the browser for that reason, configure CORS on the backend in a separate change.

## Scripts

- `npm run dev` — local development server
- `npm run build` — production build
- `npm start` — serve the production build
- `npm run lint` — ESLint
