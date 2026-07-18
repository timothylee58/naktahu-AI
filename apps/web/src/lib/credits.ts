import type { SupabaseClient } from '@supabase/supabase-js';

/** Read credit balance via Supabase RLS (no Railway JWT required). */
export async function fetchUserCredits(
  supabase: SupabaseClient,
  userId: string,
): Promise<number | null> {
  const { data, error } = await supabase
    .from('agent_credits')
    .select('credits_remaining')
    .eq('user_id', userId)
    .maybeSingle();

  if (error) {
    return null;
  }

  return typeof data?.credits_remaining === 'number' ? data.credits_remaining : 0;
}
