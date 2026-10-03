"use client";

import type { FormEvent, KeyboardEvent } from "react";
import type { ChatMode } from "@/lib/types";

type QuestionFormProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  maxLength: number;
  mode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
};

export function QuestionForm({
  value,
  onChange,
  onSubmit,
  loading,
  maxLength,
  mode,
  onModeChange,
}: QuestionFormProps) {
  const trimmed = value.trim();
  const disabled = loading || trimmed.length === 0;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled) {
      return;
    }
    onSubmit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      if (!disabled) {
        onSubmit();
      }
    }
  }

  return (
    <form
      className="question-form"
      onSubmit={handleSubmit}
      aria-busy={loading}
    >
      <div className="mode-switch" role="group" aria-label="Chat mode">
        <button
          type="button"
          className={
            mode === "chat" ? "mode-switch-button is-active" : "mode-switch-button"
          }
          aria-pressed={mode === "chat"}
          disabled={loading}
          onClick={() => onModeChange("chat")}
        >
          Chat
        </button>
        <button
          type="button"
          className={
            mode === "agent"
              ? "mode-switch-button is-active"
              : "mode-switch-button"
          }
          aria-pressed={mode === "agent"}
          disabled={loading}
          onClick={() => onModeChange("agent")}
        >
          Agent
        </button>
      </div>
      <p className="mode-switch-hint" id="mode-hint">
        {mode === "agent"
          ? "Agent mode: greetings, compare products, multi-step search."
          : "Chat mode: single-document Q&A (default)."}
      </p>

      <label htmlFor="question" className="question-label">
        Ask a question
      </label>
      <textarea
        id="question"
        className="question-input"
        name="question"
        rows={4}
        maxLength={maxLength}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          mode === "agent"
            ? "Ask, greet, or compare products…"
            : "Ask about an approved product document…"
        }
        disabled={loading}
        aria-describedby="question-hint mode-hint"
      />
      <div className="question-meta">
        <span id="question-hint" className="char-count">
          {value.length}/{maxLength}
          <span className="sr-only">
            {" "}
            Press Control or Command plus Enter to submit.
          </span>
        </span>
        <button
          type="submit"
          className="submit-button"
          disabled={disabled}
          aria-label={loading ? "Asking question" : "Ask question"}
        >
          {loading ? "Asking…" : "Ask"}
        </button>
      </div>
    </form>
  );
}
