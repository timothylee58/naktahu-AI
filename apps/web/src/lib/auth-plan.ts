import type { User } from '@supabase/supabase-js';

export const ADMIN_ROLES = new Set(['primary_admin', 'secondary_admin']);

const PLAN_RANK: Record<string, number> = {
  free: 0,
  student: 1,
  pro: 2,
  business: 3,
};

export function userRole(user: User | null | undefined): string | undefined {
  const role = user?.app_metadata?.role;
  return typeof role === 'string' ? role : undefined;
}

/** Effective plan for UI gates — mirrors API effective_plan(). */
export function effectivePlan(user: User | null | undefined): string {
  if (!user) return 'free';
  const role = userRole(user);
  if (role && ADMIN_ROLES.has(role)) return 'business';
  const plan = user.app_metadata?.plan;
  return typeof plan === 'string' ? plan : 'free';
}

export function canAccessHistory(user: User | null | undefined): boolean {
  return (PLAN_RANK[effectivePlan(user)] ?? 0) >= PLAN_RANK.pro;
}

/** Paid Developer API plans (starter/growth/etc.) require Pro+ — mirrors the
 * app's own history gate. The "free" API plan stays open to everyone. */
export function canAccessPaidDeveloperPlans(user: User | null | undefined): boolean {
  return (PLAN_RANK[effectivePlan(user)] ?? 0) >= PLAN_RANK.pro;
}

export function planBadgeLabel(user: User | null | undefined): string {
  const role = userRole(user);
  if (role === 'primary_admin') return 'primary admin';
  if (role === 'secondary_admin') return 'secondary admin';
  return effectivePlan(user);
}
