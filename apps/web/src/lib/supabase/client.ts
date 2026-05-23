import { createBrowserClient } from '@supabase/ssr';

export function createClient() {
  // Provide safe fallback values so the client never throws during
  // SSR prerendering (when env vars are absent at build time).
  const url =
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? 'https://placeholder.supabase.co';
  const key =
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? 'placeholder-anon-key';
  return createBrowserClient(url, key);
}
