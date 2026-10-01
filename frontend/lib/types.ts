export type ChatRequest = {
  question: string;
};

export type Citation = {
  product_name?: string | null;
  document_type?: string | null;
  source_filename?: string | null;
  s3_key?: string | null;
  page_number?: number | null;
  section_name?: string | null;
  document_version?: string | null;
  effective_date?: string | null;
};

export type ChatResponse = {
  answer: string;
  source: string | null;
  citations?: Citation[];
};
