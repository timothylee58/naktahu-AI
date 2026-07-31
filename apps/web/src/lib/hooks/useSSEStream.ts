'use client';

import { useCallback, useRef, useState } from 'react';
import type { Citation, SSEMetadata } from '@/lib/types';
import { API_BASE } from '@/lib/api-base';

export interface UseSSEStreamParams {
  sessionId?: string;
  language?: string;
  accessToken?: string;
}

export interface UseSSEStreamReturn {
  tokens: string[];
  citations: Citation[];
  metadata: SSEMetadata | null;
  suggestions: string[];
  isStreaming: boolean;
  error: string | null;
  startStream: (query: string, language?: string) => void;
  reset: () => void;
}

async function* readSSELines(
  response: Response,
  signal: AbortSignal,
): AsyncGenerator<{ event: string; data: string }> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';

      for (const part of parts) {
        if (!part.trim()) continue;
        let event = 'message';
        let data = '';
        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) event = line.slice(7).trim();
          else if (line.startsWith('data: ')) data = line.slice(6).trim();
        }
        yield { event, data };
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export function useSSEStream({
  sessionId,
  language: defaultLanguage = 'ms',
  accessToken,
}: UseSSEStreamParams = {}): UseSSEStreamReturn {
  const [tokens, setTokens] = useState<string[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [metadata, setMetadata] = useState<SSEMetadata | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setTokens([]);
    setCitations([]);
    setMetadata(null);
    setSuggestions([]);
    setIsStreaming(false);
    setError(null);
  }, []);

  const startStream = useCallback(
    (query: string, language?: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setTokens([]);
      setCitations([]);
      setMetadata(null);
      setSuggestions([]);
      setError(null);
      setIsStreaming(true);

      const lang = language ?? defaultLanguage;

      (async () => {
        try {
          const headers: Record<string, string> = {
            'Content-Type': 'application/json',
          };
          if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

          const response = await fetch(`${API_BASE}/api/v1/query`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              query,
              language: lang,
              domain: 'general',
              session_id: sessionId,
            }),
            signal: controller.signal,
          });

          if (!response.ok) {
            const text = await response.text().catch(() => response.statusText);
            throw new Error(`HTTP ${response.status}: ${text}`);
          }

          for await (const { event, data } of readSSELines(
            response,
            controller.signal,
          )) {
            if (event === 'token') {
              try {
                const parsed = JSON.parse(data) as { text: string };
                setTokens((prev) => [...prev, parsed.text]);
              } catch {
                setTokens((prev) => [...prev, data]);
              }
            } else if (event === 'citation') {
              try {
                const parsed = JSON.parse(data) as Citation;
                setCitations((prev) => [...prev, parsed]);
              } catch {
                /* ignore malformed */
              }
            } else if (event === 'suggestion') {
              try {
                const parsed = JSON.parse(data) as { text: string };
                setSuggestions((prev) => [...prev, parsed.text]);
              } catch {
                /* ignore malformed */
              }
            } else if (event === 'metadata') {
              try {
                const parsed = JSON.parse(data) as SSEMetadata;
                setMetadata(parsed);
              } catch {
                /* ignore */
              }
            } else if (event === 'done') {
              try {
                const parsed = JSON.parse(data) as {
                  ok: boolean;
                  citations?: Citation[];
                  metadata?: SSEMetadata;
                };
                if (parsed.citations?.length) {
                  setCitations(parsed.citations);
                }
                if (parsed.metadata) {
                  setMetadata(parsed.metadata);
                }
              } catch {
                /* ignore */
              }
              break;
            } else if (event === 'error') {
              throw new Error(data);
            }
          }
        } catch (err: unknown) {
          if (err instanceof Error && err.name === 'AbortError') return;
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          setIsStreaming(false);
        }
      })();
    },
    [defaultLanguage, sessionId, accessToken],
  );

  return { tokens, citations, metadata, suggestions, isStreaming, error, startStream, reset };
}
