export interface Citation {
  source_url: string;
  source_title: string;
  ministry: string;
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
}

export type UILocale = 'en' | 'ms';
