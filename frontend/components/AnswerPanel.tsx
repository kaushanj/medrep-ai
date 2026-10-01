type AnswerPanelProps = {
  answer: string | null;
  loading: boolean;
};

export function AnswerPanel({ answer, loading }: AnswerPanelProps) {
  if (loading) {
    return (
      <section className="panel" aria-live="polite">
        <h2 className="panel-title">Answer</h2>
        <p className="muted">Generating answer…</p>
      </section>
    );
  }

  if (!answer) {
    return null;
  }

  return (
    <section className="panel" aria-live="polite">
      <h2 className="panel-title">Answer</h2>
      <p className="answer-text">{answer}</p>
    </section>
  );
}
