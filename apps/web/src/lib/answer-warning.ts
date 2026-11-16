/**
 * When to show the "answer may be inaccurate" warning under an assistant answer.
 *
 * Confidence alone was not enough: the backend flags an answer for follow-up (`needs_clarification`)
 * when its evidence is thin, for example fewer than two supporting chunks, and the synthesiser then
 * hedges the text. That can happen at a high confidence (a correct EPF answer came back at 0.68 and
 * a correct self-relief answer at 0.83), so a bubble with hedged text and no warning contradicted
 * itself. The 0.4 cut-off for the confidence number is unchanged.
 */
export const LOW_CONFIDENCE_THRESHOLD = 0.4;

export function shouldWarnLowConfidence(
  confidence: number | null | undefined,
  needsClarification: boolean | null | undefined,
): boolean {
  if (needsClarification === true) return true;
  return typeof confidence === 'number' && confidence < LOW_CONFIDENCE_THRESHOLD;
}
