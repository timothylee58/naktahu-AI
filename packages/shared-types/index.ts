/**
 * HTTP/SSE contract of the NakTahu API (apps/api). Keep in step with
 * app/routers/query.py, routers/_request_fields.py and app/agents/router_node.py.
 */

/** Languages the router classifies a query as. */
export type Language = "bm" | "en" | "zh";

/** Languages a request may send; the API folds "ms" into "bm" before the pipeline sees it. */
export type RequestLanguage = Language | "ms";

/** Retrieval domains (router_node._VALID_DOMAINS; migrations 016, 030, 037). */
export type Domain =
  | "government"
  | "education"
  | "legal"
  | "finance"
  | "healthcare"
  | "epf"
  | "tax"
  | "business"
  | "immigration"
  | "culture"
  | "parliament"
  | "property"
  | "welfare";

/** `general` marks a query not tied to one retrieval domain. */
export type ResolvedDomain = Domain | "general";

export type SourceTier = "official" | "community";

export interface HistoryTurn {
  role: "user" | "assistant";
  /** Max 2000 characters. */
  content: string;
}

/** POST /api/v1/query body. */
export interface QueryRequest {
  /** 2-1000 characters. */
  query: string;
  /** Alphanumeric, hyphen or underscore only; max 128 characters. */
  session_id?: string;
  language?: RequestLanguage;
  /** Five digits. */
  postcode?: string;
  /** Last turns of the conversation, oldest first; max 6. */
  history?: HistoryTurn[];
}

export interface Citation {
  source_url?: string;
  source_title?: string;
  ministry: string;
  url?: string;
  title?: string;
  confidence?: number;
  stale_disclaimer?: boolean;
  /** ISO date (YYYY-MM-DD) the cited rule takes effect. Render nothing when absent. */
  effective_date?: string | null;
  /** True when the rule is announced but takes effect after today. */
  not_yet_effective?: boolean;
  /** ISO timestamp NakTahu last ingested this source. Render nothing when absent. */
  retrieved_at?: string | null;
  /** Absent when unknown: render no badge. Never infer it from the URL. */
  source_tier?: SourceTier | null;
}

/** Real agency contact for a personal-record query NakTahu cannot answer. */
export interface AgencyContact {
  agency: string;
  domain: string;
  hotline: string;
  portal: string;
}

export interface SSEMetadata {
  confidence?: number;
  domain?: ResolvedDomain;
  /** Language of the answer, detected from the query. */
  language?: Language;
  agency_contact?: AgencyContact;
  /** Evidence was thin or the answer said the context lacks it; confidence is below the 0.6 bar. */
  needs_clarification?: boolean;
  /** The finished answer said the provided context has no answer. */
  answer_declined?: boolean;
  [key: string]: unknown;
}

/** Events on the text/event-stream response of POST /api/v1/query. */
export type SSEEvent =
  | { event: "token"; data: { text: string } }
  | { event: "citation"; data: Citation }
  | { event: "suggestion"; data: { text: string } }
  | { event: "metadata"; data: SSEMetadata }
  | { event: "done"; data: Record<string, never> }
  | { event: "error"; data: { message: string } };
