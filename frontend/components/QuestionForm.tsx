"use client";

import type { FormEvent } from "react";

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

  return (
    <form className="question-form" onSubmit={handleSubmit}>
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
        placeholder="Ask about an approved product document…"
        disabled={loading}
      />
      <div className="question-meta">
        <span className="char-count">
          {value.length}/{maxLength}
        </span>
        <button type="submit" className="submit-button" disabled={disabled}>
          {loading ? "Asking…" : "Ask"}
        </button>
      </div>
    </form>
  );
}
