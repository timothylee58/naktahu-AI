/** Wired product agents — keep in sync with apps/api agent registry seeds. */

export type AgentPlanKey = 'free' | 'free_plus' | 'student' | 'business';

export interface WiredAgent {
  slug: string;
  href: string;
  planKey: AgentPlanKey;
  badgeKey?: 'new';
}

export const WIRED_AGENTS: WiredAgent[] = [
  {
    slug: 'compliance-drafter',
    href: '/agents/compliance-drafter',
    planKey: 'free_plus',
  },
  {
    slug: 'study-agent',
    href: '/agents/study-agent',
    planKey: 'student',
  },
  {
    slug: 'immigration-navigator',
    href: '/agents/immigration-navigator',
    planKey: 'free_plus',
  },
  {
    slug: 'health-triage',
    href: '/agents/health-triage',
    planKey: 'free',
  },
  {
    slug: 'grant-finder',
    href: '/agents/grant-finder',
    planKey: 'free',
    badgeKey: 'new',
  },
  {
    slug: 'research-synthesiser',
    href: '/agents/research-synthesiser',
    planKey: 'business',
  },
];

export function agentTitleKey(slug: string): string {
  return `agents.${slug}.title`;
}

export function agentDescKey(slug: string): string {
  return `agents.${slug}.desc`;
}

export function agentPlanKey(planKey: AgentPlanKey): string {
  return `agents.plan.${planKey}`;
}
