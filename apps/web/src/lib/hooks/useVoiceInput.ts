'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseVoiceInputParams {
  language?: string;
}

export interface UseVoiceInputReturn {
  isListening: boolean;
  transcript: string;
  error: string | null;
  startListening: () => void;
  stopListening: () => void;
  isSupported: boolean;
}

interface ISpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly 0: { readonly transcript: string };
}

interface ISpeechRecognitionResultList {
  readonly length: number;
  readonly [i: number]: ISpeechRecognitionResult;
}

interface ISpeechRecognitionEvent {
  readonly resultIndex: number;
  readonly results: ISpeechRecognitionResultList;
}

interface ISpeechRecognitionErrorEvent {
  readonly error: string;
}

interface ISpeechRecognition extends EventTarget {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onstart: (() => void) | null;
  onresult: ((event: ISpeechRecognitionEvent) => void) | null;
  onerror: ((event: ISpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

type ISpeechRecognitionCtor = new () => ISpeechRecognition;

declare global {
  interface Window {
    SpeechRecognition?: ISpeechRecognitionCtor;
    webkitSpeechRecognition?: ISpeechRecognitionCtor;
  }
}

function getSR(): ISpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

// Map app locale to BCP-47 tags recognised by the Web Speech API
function toBcp47(language: string): string {
  const map: Record<string, string> = {
    'ms-MY': 'ms-MY',
    'en-MY': 'en-MY',
    'zh-MY': 'zh-CN', // zh-MY is not a valid tag — use zh-CN (Simplified Mandarin)
    'zh-CN': 'zh-CN',
    'zh-TW': 'zh-TW',
  };
  return map[language] ?? language;
}

export function useVoiceInput({
  language = 'ms-MY',
}: UseVoiceInputParams = {}): UseVoiceInputReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef<ISpeechRecognition | null>(null);

  useEffect(() => {
    setIsSupported(getSR() !== null);
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const startListening = useCallback(() => {
    const Ctor = getSR();
    if (!Ctor) return;
    if (recognitionRef.current) {
      recognitionRef.current.onstart = null;
      recognitionRef.current.onresult = null;
      recognitionRef.current.onerror = null;
      recognitionRef.current.onend = null;
      recognitionRef.current.abort();
    }
    setError(null);

    const rec = new Ctor();
    rec.lang = toBcp47(language);
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = false;

    rec.onstart = () => setIsListening(true);
    rec.onresult = (e: ISpeechRecognitionEvent) => {
      let interim = '';
      let final = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) final += r[0].transcript;
        else interim += r[0].transcript;
      }
      setTranscript(final || interim);
    };
    rec.onerror = (e: ISpeechRecognitionErrorEvent) => {
      setIsListening(false);
      // 'no-speech' and 'aborted' are benign
      if (e.error !== 'no-speech' && e.error !== 'aborted') {
        setError(e.error);
      }
    };
    rec.onend = () => setIsListening(false);

    recognitionRef.current = rec;
    setTranscript('');
    rec.start();
  }, [language]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  return { isListening, transcript, error, startListening, stopListening, isSupported };
}
