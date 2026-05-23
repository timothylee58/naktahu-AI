export type Domain =
  | "government"
  | "education"
  | "legal"
  | "finance"
  | "health"
  | "culture";

export type Language = "bm" | "en";

export interface Citation {
  title: string;
  ministry: string;
  url: string;
  confidence: number;
}

export interface SSEEvent {
  type: "token" | "citation" | "metadata" | "done" | "error";
  data:
    | { text: string }
    | Citation
    | { confidence: number; domain: Domain; language: Language }
    | Record<string, never>
    | { message: string };
}

export interface QueryRequest {
  query: string;
  sessionId: string;
  userId?: string;
}

export interface QueryResponse {
  sessionId: string;
  citations: Citation[];
  confidence: number;
  domain: Domain;
  language: Language;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  timestamp: string;
}

export interface UserSession {
  sessionId: string;
  userId?: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}
