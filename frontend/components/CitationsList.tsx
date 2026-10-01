import type { Citation } from "@/lib/types";

type CitationsListProps = {
  citations: Citation[];
  source: string | null;
  visible: boolean;
};

const CITATION_FIELDS: Array<{
  key: keyof Citation;
  label: string;
}> = [
  { key: "product_name", label: "Product" },
  { key: "document_type", label: "Document type" },
  { key: "source_filename", label: "Filename" },
  { key: "s3_key", label: "S3 key" },
  { key: "page_number", label: "Page" },
  { key: "section_name", label: "Section" },
  { key: "document_version", label: "Version" },
  { key: "effective_date", label: "Effective date" },
];

function hasAnyField(citation: Citation): boolean {
  return CITATION_FIELDS.some(({ key }) => {
    const value = citation[key];
    return value !== null && value !== undefined && value !== "";
  });
}

export function CitationsList({
  citations,
  source,
  visible,
}: CitationsListProps) {
  if (!visible) {
    return null;
  }

  const hasCitations = citations.length > 0;

  return (
    <section className="panel" aria-labelledby="sources-heading">
      <h2 id="sources-heading" className="panel-title">
        Sources
      </h2>

      {!hasCitations && (
        <p className="muted">No structured citations returned.</p>
      )}

      {hasCitations && (
        <ol className="citations-list">
          {citations.map((citation, index) => (
            <li key={index} className="citation-item">
              {hasAnyField(citation) ? (
                <dl className="citation-fields">
                  {CITATION_FIELDS.map(({ key, label }) => {
                    const value = citation[key];
                    if (value === null || value === undefined || value === "") {
                      return null;
                    }
                    return (
                      <div key={key} className="citation-field">
                        <dt>{label}</dt>
                        <dd>{String(value)}</dd>
                      </div>
                    );
                  })}
                </dl>
              ) : (
                <p className="muted">Citation with no metadata</p>
              )}
            </li>
          ))}
        </ol>
      )}

      {source && (
        <div className="legacy-source">
          <h3 className="legacy-source-title">Source text</h3>
          <p className="legacy-source-text">{source}</p>
        </div>
      )}
    </section>
  );
}
