'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { PERSONA_STORAGE_KEY, parsePersonas, type PersonaId } from '@/lib/persona';

function readLocal(): PersonaId[] {
  try {
    return parsePersonas(JSON.parse(window.localStorage.getItem(PERSONA_STORAGE_KEY) ?? '[]'));
  } catch {
    return [];
  }
}

// Every usePersona() caller keeps its own state (the tour and the chat
// starters are siblings, not parent/child), so writes are broadcast to keep
// them in step within the tab; the native 'storage' event covers other tabs.
const CHANGE_EVENT = 'nk-personas-changed';

function writeLocal(personas: PersonaId[]): void {
  try {
    window.localStorage.setItem(PERSONA_STORAGE_KEY, JSON.stringify(personas));
  } catch {
    /* storage blocked — in-memory state still works for this session */
  }
  window.dispatchEvent(new CustomEvent<PersonaId[]>(CHANGE_EVENT, { detail: personas }));
}

// Personas are UI personalisation only (starter questions), so they live in
// Supabase user_metadata + a localStorage mirror rather than a table: no
// migration, works signed-out, and nothing server-side trusts the value.
export function usePersona() {
  const { supabase, user, ready } = useSupabaseSession();
  const [personas, setPersonasState] = useState<PersonaId[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const personasRef = useRef<PersonaId[]>([]);
  personasRef.current = personas;

  useEffect(() => {
    setPersonasState(readLocal());
    const onChange = (e: Event) => setPersonasState(parsePersonas((e as CustomEvent<unknown>).detail));
    const onStorage = (e: StorageEvent) => {
      if (e.key === PERSONA_STORAGE_KEY) setPersonasState(readLocal());
    };
    window.addEventListener(CHANGE_EVENT, onChange);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onChange);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  useEffect(() => {
    if (!ready || !user) return;
    const remote = parsePersonas(user.user_metadata?.personas);
    if (remote.length > 0) {
      setPersonasState(remote);
      writeLocal(remote);
      return;
    }
    // Choices made signed-out (e.g. in the first-visit tour) follow the user
    // into their account the first time they sign in.
    const local = readLocal();
    if (local.length > 0) void supabase.auth.updateUser({ data: { personas: local } });
  }, [ready, user, supabase]);

  const setPersonas = useCallback(
    async (next: PersonaId[]) => {
      const previous = personasRef.current;
      setPersonasState(next);
      writeLocal(next);
      setSaveError(false);
      if (!user) return;
      setSaving(true);
      const { error } = await supabase.auth.updateUser({ data: { personas: next } });
      setSaving(false);
      if (error) {
        setPersonasState(previous);
        writeLocal(previous);
        setSaveError(true);
      }
    },
    [supabase, user],
  );

  return { personas, setPersonas, saving, saveError, signedIn: !!user };
}
