import { type NextRequest } from 'next/server';
import { updateSession } from '@/lib/supabase/middleware';

/**
 * Root Next.js middleware — refreshes the Supabase auth session on navigation
 * so logged-in state survives token expiry and server-rendered pages. Without
 * this, `lib/supabase/middleware.updateSession` never runs and sessions silently
 * go stale. It no-ops when Supabase is unconfigured (see updateSession).
 */
export async function middleware(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: [
    // Everything except Next internals, the auth callback (handles its own
    // code exchange), and static assets.
    '/((?!_next/static|_next/image|favicon.ico|auth/callback|icons|manifest.json|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
};
