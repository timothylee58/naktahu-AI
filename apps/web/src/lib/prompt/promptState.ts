import { hasMyKad, stripMyKad } from './piiGuard';

export const PROMPT_MAX_LENGTH = 1000;

export interface PromptState {
  value: string;
  /** True once the user has seen the personal-data warning for this text. */
  piiAcknowledged: boolean;
}

export type PromptAction =
  | { type: 'type'; value: string }
  | { type: 'fill'; value: string }
  | { type: 'clear' }
  | { type: 'stripPii' }
  | { type: 'acknowledgePii' };

export const initialPromptState: PromptState = { value: '', piiAcknowledged: false };

export function promptReducer(state: PromptState, action: PromptAction): PromptState {
  switch (action.type) {
    case 'type':
    case 'fill':
      // Any edit invalidates a previous acknowledgement: new text, new warning.
      return { value: action.value.slice(0, PROMPT_MAX_LENGTH), piiAcknowledged: false };
    case 'clear':
      return initialPromptState;
    case 'stripPii':
      return { value: stripMyKad(state.value), piiAcknowledged: false };
    case 'acknowledgePii':
      return { ...state, piiAcknowledged: true };
  }
}

export type SubmitDecision =
  | { kind: 'ignore' }
  | { kind: 'warn' }
  | { kind: 'send'; text: string };

/** First Enter on text containing a MyKad number warns; the second sends. */
export function decideSubmit(state: PromptState): SubmitDecision {
  const text = state.value.trim();
  if (!text) return { kind: 'ignore' };
  if (hasMyKad(text) && !state.piiAcknowledged) return { kind: 'warn' };
  return { kind: 'send', text };
}

/** Enter is also how CJK input methods commit a candidate; never send mid-composition. */
export function isComposingEnter(e: { nativeEvent?: { isComposing?: boolean }; keyCode?: number }): boolean {
  return e.nativeEvent?.isComposing === true || e.keyCode === 229;
}
