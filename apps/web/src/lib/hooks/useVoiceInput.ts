'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '@/lib/api-base';

export interface UseVoiceInputParams {
  language?: string;
}

export interface UseVoiceInputReturn {
  isListening: boolean;
  transcript: string;
  error: string | null;
  startListening: () => void;
  stopListening: () => void;
  /** Web Speech API available (Chromium/Safari). */
  isSupported: boolean;
  /** Any voice path available — Web Speech OR the server transcription fallback. */
  available: boolean;
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

// Collapse a BCP-47 tag to the app locale the /transcribe endpoint expects.
function toApiLanguage(language: string): 'bm' | 'en' | 'zh' {
  const lower = language.toLowerCase();
  if (lower.startsWith('ms')) return 'bm';
  if (lower.startsWith('zh') || lower.startsWith('cmn')) return 'zh';
  return 'en';
}

const MIC_RECORD_MIME = 'audio/webm;codecs=opus';

function canRecordAudio(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined' &&
    (MediaRecorder.isTypeSupported?.('audio/webm') ?? false)
  );
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onloadend = () => {
      const result = String(reader.result);
      resolve(result.slice(result.indexOf(',') + 1)); // strip the data: prefix
    };
    reader.readAsDataURL(blob);
  });
}

export function useVoiceInput({
  language = 'ms-MY',
}: UseVoiceInputParams = {}): UseVoiceInputReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSupported, setIsSupported] = useState(false);
  // Server-transcription fallback (MediaRecorder → /api/v1/transcribe).
  const [recordSupported, setRecordSupported] = useState(false);
  const [transcribeAvailable, setTranscribeAvailable] = useState(true);
  const recognitionRef = useRef<ISpeechRecognition | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    setIsSupported(getSR() !== null);
    setRecordSupported(canRecordAudio());
  }, []);

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  // Assemble the recording, send it to the server, surface the transcript.
  const handleRecordingStop = useCallback(async () => {
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
    chunksRef.current = [];
    stopTracks();
    if (blob.size === 0) return;
    try {
      const audio_base64 = await blobToBase64(blob);
      const res = await fetch(`${API_BASE}/api/v1/transcribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_base64, language: toApiLanguage(language) }),
      });
      if (res.status === 503) {
        // Transcription not configured — stop offering the fallback mic.
        setTranscribeAvailable(false);
        return;
      }
      if (!res.ok) {
        setError('transcribe-failed');
        return;
      }
      const data = (await res.json()) as { transcript?: string };
      if (data.transcript) setTranscript(data.transcript);
    } catch {
      setError('transcribe-failed');
    }
  }, [language, stopTracks]);

  const startRecording = useCallback(async () => {
    setError(null);
    setTranscript('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = MediaRecorder.isTypeSupported(MIC_RECORD_MIME)
        ? MIC_RECORD_MIME
        : 'audio/webm';
      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = handleRecordingStop;
      recorderRef.current = recorder;
      recorder.start();
      setIsListening(true);
    } catch {
      setError('not-allowed');
      setIsListening(false);
      stopTracks();
    }
  }, [handleRecordingStop, stopTracks]);

  const stopListening = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop(); // fires onstop → handleRecordingStop
      setIsListening(false);
      return;
    }
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const startListening = useCallback(() => {
    const Ctor = getSR();
    if (!Ctor) {
      // No Web Speech API — fall back to server transcription if possible.
      if (recordSupported && transcribeAvailable) void startRecording();
      return;
    }
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
  }, [language, recordSupported, transcribeAvailable, startRecording]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
      stopTracks();
    };
  }, [stopTracks]);

  const available = isSupported || (recordSupported && transcribeAvailable);

  return {
    isListening,
    transcript,
    error,
    startListening,
    stopListening,
    isSupported,
    available,
  };
}
