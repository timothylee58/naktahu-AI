export type {
  AgencyContact,
  Citation,
  SourceTier,
  SSEMetadata,
} from '@naktahu/shared-types';

import type { AgencyContact, Citation } from '@naktahu/shared-types';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tokens: string[];
  citations: Citation[];
  confidence: number | null;
  /** Backend flagged this answer for follow-up; shows the warning even at a high confidence. */
  needsClarification?: boolean;
  isStreaming: boolean;
  /** For assistant messages: the user query this answered, plus its resolved domain/language. Used for feedback submission. */
  query?: string;
  domain?: string;
  language?: string;
  suggestions?: string[];
  agencyContact?: AgencyContact;
  /** True when this assistant message is a stream/network failure, not a
   * real answer — rendered distinctly (error styling + explicit retry)
   * instead of looking like a normal completed response. */
  isError?: boolean;
}

export type UILocale = 'en' | 'ms' | 'zh';
