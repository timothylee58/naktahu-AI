export interface Citation {
  source_url?: string;
  source_title?: string;
  ministry: string;
  url?: string;
  title?: string;
  confidence?: number;
  stale_disclaimer?: boolean;
}

export interface SSEMetadata {
  detectedLanguage?: string;
  confidence?: number;
  domain?: string;
  [key: string]: unknown;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tokens: string[];
  citations: Citation[];
  confidence: number | null;
  isStreaming: boolean;
  /** For assistant messages: the user query this answered, plus its resolved domain/language. Used for feedback submission. */
  query?: string;
  domain?: string;
  language?: string;
}

export type UILocale = 'en' | 'ms' | 'zh';
