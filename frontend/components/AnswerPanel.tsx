type AnswerPanelProps = {
  answer: string | null;
  loading: boolean;
  hasError?: boolean;
};

export function AnswerPanel({ answer, loading, hasError = false }: AnswerPanelProps) {
  if (loading) {
    return (
      <section className="panel" aria-live="polite" aria-busy="true">
        <h2 className="panel-title">Answer</h2>
        <p className="muted">Generating answer…</p>
      </section>
    );
  }

  if (!answer) {
    if (hasError) {
      return null;
    }
    return (
      <section className="panel" aria-live="polite">
        <h2 className="panel-title">Answer</h2>
        <p className="muted">Ask a question to see the answer here.</p>
      </section>
    );
  }

  return (
    <section className="panel" aria-live="polite">
      <h2 className="panel-title">Answer</h2>
      <p className="answer-text">{answer}</p>
    </section>
  );
}
