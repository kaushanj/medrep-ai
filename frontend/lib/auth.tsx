"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const GIS_SCRIPT_SRC = "https://accounts.google.com/gsi/client";
const MISSING_CLIENT_ID_MESSAGE =
  "Google sign-in is not configured. Set NEXT_PUBLIC_GOOGLE_CLIENT_ID in .env.local (see README).";
const SIGN_IN_ERROR_MESSAGE =
  "Google sign-in failed. Please try again.";
const SCRIPT_LOAD_ERROR_MESSAGE =
  "Could not load Google sign-in. Check your network and try again.";

export type AuthUser = {
  email: string;
  name: string;
  picture?: string;
};

export type AuthStatus =
  | "loading"
  | "unauthenticated"
  | "authenticated"
  | "misconfigured";

export type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  idToken: string | null;
  error: string | null;
  /** Clears session; optional message is shown on the sign-in screen (e.g. session expired). */
  signOut: (message?: string) => void;
  /** Host element for the official GIS button when status is unauthenticated. */
  setButtonHost: (el: HTMLDivElement | null) => void;
};

type JwtDisplayClaims = {
  email?: string;
  name?: string;
  picture?: string;
};

let currentIdToken: string | null = null;

/** Module-level accessor for the current Google ID token (for #35 API client). */
export function getIdToken(): string | null {
  return currentIdToken;
}

function setCurrentIdToken(token: string | null) {
  currentIdToken = token;
}

function decodeJwtPayload(token: string): JwtDisplayClaims | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2 || !parts[1]) {
      return null;
    }
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = atob(padded);
    return JSON.parse(json) as JwtDisplayClaims;
  } catch {
    return null;
  }
}

function userFromCredential(credential: string): AuthUser | null {
  const claims = decodeJwtPayload(credential);
  if (!claims?.email) {
    return null;
  }
  return {
    email: claims.email,
    name: claims.name?.trim() || claims.email,
    picture: claims.picture,
  };
}

function loadGisScript(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("GIS requires a browser"));
  }
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }

  const existing = document.querySelector<HTMLScriptElement>(
    `script[src="${GIS_SCRIPT_SRC}"]`
  );
  if (existing) {
    return new Promise((resolve, reject) => {
      if (window.google?.accounts?.id) {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener(
        "error",
        () => reject(new Error(SCRIPT_LOAD_ERROR_MESSAGE)),
        { once: true }
      );
    });
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GIS_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(SCRIPT_LOAD_ERROR_MESSAGE));
    document.head.appendChild(script);
  });
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim() ?? "";

  const [status, setStatus] = useState<AuthStatus>(() =>
    clientId ? "loading" : "misconfigured"
  );
  const [user, setUser] = useState<AuthUser | null>(null);
  const [idToken, setIdToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(() =>
    clientId ? null : MISSING_CLIENT_ID_MESSAGE
  );
  const [buttonHost, setButtonHost] = useState<HTMLDivElement | null>(null);

  const clearSession = useCallback(() => {
    setCurrentIdToken(null);
    setIdToken(null);
    setUser(null);
  }, []);

  const signOut = useCallback(
    (message?: string) => {
      clearSession();
      try {
        window.google?.accounts?.id?.disableAutoSelect();
      } catch {
        // ignore GIS cleanup failures
      }
      setStatus(clientId ? "unauthenticated" : "misconfigured");
      if (!clientId) {
        setError(MISSING_CLIENT_ID_MESSAGE);
      } else {
        setError(message ?? null);
      }
    },
    [clearSession, clientId]
  );

  const handleCredential = useCallback(
    (response: GoogleCredentialResponse) => {
      const credential = response.credential;
      if (!credential) {
        setError(SIGN_IN_ERROR_MESSAGE);
        setStatus("unauthenticated");
        clearSession();
        return;
      }

      const nextUser = userFromCredential(credential);
      if (!nextUser) {
        setError(SIGN_IN_ERROR_MESSAGE);
        setStatus("unauthenticated");
        clearSession();
        return;
      }

      setCurrentIdToken(credential);
      setIdToken(credential);
      setUser(nextUser);
      setError(null);
      setStatus("authenticated");
    },
    [clearSession]
  );

  useEffect(() => {
    if (!clientId) {
      setStatus("misconfigured");
      setError(MISSING_CLIENT_ID_MESSAGE);
      clearSession();
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        await loadGisScript();
        if (cancelled) {
          return;
        }
        if (!window.google?.accounts?.id) {
          throw new Error(SCRIPT_LOAD_ERROR_MESSAGE);
        }
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: handleCredential,
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        if (!cancelled) {
          setStatus((prev) =>
            prev === "authenticated" ? prev : "unauthenticated"
          );
        }
      } catch {
        if (!cancelled) {
          setError(SCRIPT_LOAD_ERROR_MESSAGE);
          setStatus("unauthenticated");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [clientId, handleCredential, clearSession]);

  useEffect(() => {
    if (status !== "unauthenticated" || !buttonHost || !clientId) {
      return;
    }
    if (!window.google?.accounts?.id) {
      return;
    }

    buttonHost.innerHTML = "";
    window.google.accounts.id.renderButton(buttonHost, {
      type: "standard",
      theme: "outline",
      size: "large",
      text: "signin_with",
      shape: "rectangular",
      width: 280,
    });
  }, [status, buttonHost, clientId]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      idToken,
      error,
      signOut,
      setButtonHost,
    }),
    [status, user, idToken, error, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
