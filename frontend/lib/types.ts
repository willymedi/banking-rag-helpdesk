export type Citation = {
  doc_id: string;
  doc_title: string;
  section_title: string;
  chunk_id: string;
  snippet: string;
  offset_start?: number;
  offset_end?: number;
};

export type QueryResult = {
  query_id: string;
  trace_id: string;
  answer: string;
  citations: Citation[];
  participating_agents: string[];
  confidence: number;
  sufficient_context: boolean;
  blocked_reason: string;
  routing_reasoning?: string;
};
