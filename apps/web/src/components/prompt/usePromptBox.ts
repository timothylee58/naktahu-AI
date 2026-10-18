'use client';

import { useCallback, useReducer } from 'react';
import {
  decideSubmit,
  initialPromptState,
  promptReducer,
} from '@/lib/prompt/promptState';
import { hasMyKad } from '@/lib/prompt/piiGuard';

interface UsePromptBoxOptions {
  onSend: (text: string) => void;
  /** Empty the box once sent. The homepage keeps its text while the route
   * changes; the chat dock must clear so the next question starts blank. */
  clearOnSend?: boolean;
}

export function usePromptBox({ onSend, clearOnSend = false }: UsePromptBoxOptions) {
  const [state, dispatch] = useReducer(promptReducer, initialPromptState);

  const type = useCallback((value: string) => dispatch({ type: 'type', value }), []);
  const fill = useCallback((value: string) => dispatch({ type: 'fill', value }), []);
  const clear = useCallback(() => dispatch({ type: 'clear' }), []);
  const stripPii = useCallback(() => dispatch({ type: 'stripPii' }), []);

  const submit = useCallback(() => {
    const decision = decideSubmit(state);
    if (decision.kind === 'warn') dispatch({ type: 'acknowledgePii' });
    else if (decision.kind === 'send') {
      onSend(decision.text);
      if (clearOnSend) dispatch({ type: 'clear' });
    }
  }, [state, onSend, clearOnSend]);

  return {
    value: state.value,
    // Shown from the moment a number is typed, before any submit attempt.
    piiDetected: hasMyKad(state.value),
    type,
    fill,
    clear,
    stripPii,
    submit,
  };
}
