'use client';

import { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/api-base';
import { useI18n } from '@/lib/i18n';
import { resolveStateFromPostcode } from '@/lib/postcode';

const STORAGE_KEY = 'naktahu_postcode_state';
// The postcode itself, kept alongside the state so a returning visitor's MP
// lookup can be re-run without asking for it again.
const POSTCODE_KEY = 'naktahu_postcode';

interface PostcodeMp {
  full_name: string;
  salutation: string | null;
  constituency_code: string;
  constituency_name: string;
  party: string | null;
  office_address: string | null;
  office_phone: string | null;
  office_email: string | null;
}

/** MPs whose seat the postcode falls in (GET /api/v1/parliament/postcode).
 * Empty on any failure or when the postcode -> seat data has no rows for it:
 * the caller then keeps the state-only line, never a guessed MP. */
async function fetchMpsForPostcode(postcode: string): Promise<PostcodeMp[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/parliament/postcode/${encodeURIComponent(postcode)}`);
    if (!res.ok) return [];
    const body = (await res.json()) as { mps?: PostcodeMp[] };
    return Array.isArray(body.mps) ? body.mps : [];
  } catch {
    return [];
  }
}

/** Reads the remembered state id from a prior visit. Never throws — private
 * browsing / strict-privacy modes can make localStorage inaccessible, and a
 * personalization nicety must degrade to "nothing remembered", not crash the
 * landing page. */
function readStoredState(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function readStoredPostcode(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(POSTCODE_KEY);
  } catch {
    return null;
  }
}

function writeStoredState(stateId: string, postcode: string) {
  try {
    localStorage.setItem(STORAGE_KEY, stateId);
    localStorage.setItem(POSTCODE_KEY, postcode);
  } catch {
    // Same as above — best-effort only, the input still works without it.
  }
}

function clearStored() {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(POSTCODE_KEY);
  } catch {
    /* best-effort, see writeStoredState */
  }
}

interface PostcodePersonalizerProps {
  className?: string;
  inputClassName?: string;
}

/** Postcode → state personalization. Resolves a postcode to a state and
 * remembers it locally so a returning visitor sees a state-aware welcome
 * line without re-entering it — no backend call, no account required. */
export function PostcodePersonalizer({ className, inputClassName }: PostcodePersonalizerProps) {
  const { t } = useI18n();
  const [postcode, setPostcode] = useState('');
  const [stateId, setStateId] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [mps, setMps] = useState<PostcodeMp[]>([]);

  function lookUpMps(code: string) {
    setMps([]);
    void fetchMpsForPostcode(code).then(setMps);
  }

  useEffect(() => {
    const stored = readStoredState();
    if (stored) setStateId(stored);
    const storedPostcode = readStoredPostcode();
    if (stored && storedPostcode) lookUpMps(storedPostcode);
  }, []);

  function tryResolve(value: string) {
    const resolved = resolveStateFromPostcode(value);
    if (!resolved) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setStateId(resolved);
    writeStoredState(resolved, value.trim());
    lookUpMps(value.trim());
  }

  // Explicit submit still works (desktop Enter key), but the primary path is
  // auto-resolving the moment a plausible 5-digit code is typed — a numeric
  // mobile keypad often has no "Go"/"Enter" affordance wired to form submit,
  // so requiring it left the control looking broken on touch devices
  // (Cursor Bugbot finding on PR #202).
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    tryResolve(postcode);
  }

  if (stateId) {
    const stateLabel = t(`agents.welfare-eligibility.state.${stateId}`);
    // The MP line only appears when the postcode -> seat crosswalk
    // (migration 054) has a real mapping for this postcode. Otherwise the
    // visitor sees the state line alone — a postcode prefix only proves the
    // state, so we never guess an MP from it.
    return (
      <div className={`${className ?? ''} flex-col`}>
        <p>
          {t('landing.postcode.personalized').replace('{state}', stateLabel)}{' '}
          <button
            type="button"
            onClick={() => {
              setStateId(null);
              setMps([]);
              clearStored();
            }}
            className="underline underline-offset-2 opacity-70 hover:opacity-100"
          >
            {t('landing.postcode.change')}
          </button>
        </p>
        {mps.length > 0 && (
          <div className="mt-1 flex flex-col items-center gap-2 text-xs">
            <p className="font-medium">
              {mps.length > 1
                ? t('landing.postcode.spans_seats').replace('{count}', String(mps.length))
                : t('landing.postcode.your_mp')}
            </p>
            <ul className="flex flex-col items-center gap-2">
              {mps.map((mp) => {
                const contact = [mp.office_phone, mp.office_email].filter(Boolean).join(' · ');
                return (
                  <li key={mp.constituency_code} className="flex flex-col items-center leading-snug">
                    <span>
                      {[mp.salutation, mp.full_name].filter(Boolean).join(' ')}
                      {mp.party ? ` (${mp.party})` : ''}
                    </span>
                    <span className="opacity-70">
                      {mp.constituency_code} {mp.constituency_name}
                    </span>
                    {mp.office_address || contact ? (
                      <span className="opacity-70">
                        {[mp.office_address, contact].filter(Boolean).join(' — ')}
                      </span>
                    ) : (
                      <span className="opacity-50">{t('landing.postcode.no_office')}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className={className}>
      <input
        type="text"
        inputMode="numeric"
        maxLength={5}
        value={postcode}
        onChange={(e) => {
          const digits = e.target.value.replace(/\D/g, '').slice(0, 5);
          setPostcode(digits);
          setInvalid(false);
          if (digits.length === 5) tryResolve(digits);
        }}
        placeholder={t('landing.postcode.placeholder')}
        aria-label={t('landing.postcode.placeholder')}
        aria-invalid={invalid}
        className={inputClassName}
      />
      {invalid && (
        <span role="alert" className="text-[11px] text-red-500 dark:text-red-400">
          {t('landing.postcode.invalid')}
        </span>
      )}
    </form>
  );
}
