"use client";

import { useState } from "react";
import { AnswerPanel } from "@/components/AnswerPanel";
import { CitationsList } from "@/components/CitationsList";
import { QuestionForm } from "@/components/QuestionForm";
import { SignInScreen } from "@/components/SignInScreen";
import { UserMenu } from "@/components/UserMenu";
import { useAuth } from "@/lib/auth";
import { askChat, AuthError } from "@/lib/api";
import type { Citation } from "@/lib/types";

const MAX_QUESTION_LENGTH = 2000;

export default function HomePage() {
  const { status, signOut } = useAuth();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [hasResponse, setHasResponse] = useState(false);

  if (status !== "authenticated") {
    return <SignInScreen />;
  }

  async function handleSubmit() {
    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer(null);
    setSource(null);
    setCitations([]);
    setHasResponse(false);

    try {
      const response = await askChat(trimmed);
      setAnswer(response.answer);
      setSource(response.source);
      setCitations(response.citations ?? []);
      setHasResponse(true);
    } catch (err) {
      if (err instanceof AuthError) {
        signOut();
        return;
      }
      const message =
        err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      setHasResponse(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <header className="page-header">
        <div className="page-header-row">
          <div className="page-header-copy">
            <h1 className="page-title">MedRep AI</h1>
            <p className="page-subtitle">
              Ask questions about approved product documents.
            </p>
          </div>
          <UserMenu />
        </div>
      </header>

      <QuestionForm
        value={question}
        onChange={setQuestion}
        onSubmit={handleSubmit}
        loading={loading}
        maxLength={MAX_QUESTION_LENGTH}
      />

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      <AnswerPanel answer={answer} loading={loading} />

      <CitationsList
        citations={citations}
        source={source}
        visible={hasResponse && !loading}
      />
    </main>
  );
}
