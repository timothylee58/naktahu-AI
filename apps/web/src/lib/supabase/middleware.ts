import { createServerClient } from '@supabase/ssr';
import { type NextRequest, NextResponse } from 'next/server';

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? '';
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? '';

  // Skip when Supabase isn't really configured (missing/placeholder) so an
  // unreachable host can't 500 every request in dev or during previews.
  if (!url || !key || url.includes('placeholder')) {
    return supabaseResponse;
  }

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet: Array<{ name: string; value: string; options?: Record<string, unknown> }>) {
        cookiesToSet.forEach(({ name, value }) =>
          request.cookies.set(name, value),
        );
        supabaseResponse = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options as Parameters<typeof supabaseResponse.cookies.set>[2]),
        );
      },
    },
  });

  // Refresh the session — do not remove, critical for keeping auth alive.
  // Guarded so a transient Supabase/network error never breaks the request.
  try {
    await supabase.auth.getUser();
  } catch {
    // ignore — a failed refresh must not take down every route
  }

  return supabaseResponse;
}
