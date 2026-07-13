/** Rotating hero/footer taglines — keys map to i18n strings per locale. */
export const LANDING_TAGLINE_KEYS = [
  'landing.tagline.01',
  'landing.tagline.02',
  'landing.tagline.03',
  'landing.tagline.04',
  'landing.tagline.05',
  'landing.tagline.06',
  'landing.tagline.07',
  'landing.tagline.08',
  'landing.tagline.09',
  'landing.tagline.10',
  'landing.tagline.11',
  'landing.tagline.12',
] as const;

export type LandingTaglineKey = (typeof LANDING_TAGLINE_KEYS)[number];

export function pickRandomTaglineKey(): LandingTaglineKey {
  const index = Math.floor(Math.random() * LANDING_TAGLINE_KEYS.length);
  return LANDING_TAGLINE_KEYS[index] ?? 'landing.tagline.01';
}
