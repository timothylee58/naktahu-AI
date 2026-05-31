import { type NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/chat';
  const oauthError = searchParams.get('error');
  const oauthErrorDesc = searchParams.get('error_description');

  if (oauthError) {
    const url = new URL('/?error=auth', origin);
    url.searchParams.set('reason', oauthError);
    if (oauthErrorDesc) url.searchParams.set('detail', oauthErrorDesc);
    return NextResponse.redirect(url);
  }

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(next, origin));
    }
  }

  return NextResponse.redirect(new URL('/?error=auth', origin));
}
