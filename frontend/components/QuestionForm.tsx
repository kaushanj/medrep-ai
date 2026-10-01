"use client";

import type { FormEvent, KeyboardEvent } from "react";

type QuestionFormProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  maxLength: number;
};

export function QuestionForm({
  value,
  onChange,
  onSubmit,
  loading,
  maxLength,
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
        placeholder="Ask about an approved product document…"
        disabled={loading}
        aria-describedby="question-hint"
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
