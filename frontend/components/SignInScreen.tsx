"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "@/lib/auth";

export function SignInScreen() {
  const { status, error, setButtonHost } = useAuth();
  const buttonRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setButtonHost(buttonRef.current);
    return () => setButtonHost(null);
  }, [setButtonHost, status]);

  const showButton = status === "unauthenticated" || status === "loading";

  return (
    <main className="sign-in-page">
      <section className="sign-in-panel" aria-labelledby="sign-in-title">
        <h1 id="sign-in-title" className="sign-in-title">
          MedRep AI
        </h1>
        <p className="sign-in-subtitle">
          Sign in with Google to ask questions about approved product documents.
        </p>

        {status === "misconfigured" && (
          <div className="error-banner" role="alert">
            {error ??
              "Google sign-in is not configured. Set NEXT_PUBLIC_GOOGLE_CLIENT_ID in .env.local."}
          </div>
        )}

        {status !== "misconfigured" && error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}

        {status === "loading" && (
          <p className="muted sign-in-loading">Loading sign-in…</p>
        )}

        {showButton && (
          <div
            className="google-button-host"
            ref={buttonRef}
            aria-label="Google sign-in"
          />
        )}
      </section>
    </main>
  );
}
