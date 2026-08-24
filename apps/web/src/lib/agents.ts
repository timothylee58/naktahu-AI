/** Wired product agents — keep in sync with apps/api agent registry seeds. */

// Matches middleware/plan_gate._PLAN_RANK and services/agent_registry.py's
// plan_required values — NOT a separate frontend taxonomy. "free_plus" used
// to exist here and didn't correspond to anything in the backend; the plan
// values below are copied directly from the live `agents` table.
export type AgentPlanKey = 'free' | 'student' | 'pro' | 'business';

export interface WiredAgent {
  slug: string;
  href: string;
  planKey: AgentPlanKey;
  badgeKey?: 'new';
  /** The agent's actual registered name in apps/api's agents table, used to
   * call /api/v1/agents/{name}/... and to look up real accessible/
   * plan_required data from GET /api/v1/agents. Defaults to `slug` when the
   * two already match. grant-finder is the one exception: the frontend
   * route/slug is grant-finder, but the backend agent it actually drives is
   * eligibility-agent (there is no registered "grant-finder" agent). */
  backendName?: string;
}

export const WIRED_AGENTS: WiredAgent[] = [
  {
    slug: 'compliance-drafter',
    href: '/agents/compliance-drafter',
    planKey: 'free',
  },
  {
    slug: 'study-agent',
    href: '/agents/study-agent',
    planKey: 'student',
  },
  {
    slug: 'immigration-navigator',
    href: '/agents/immigration-navigator',
    planKey: 'free',
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
    backendName: 'eligibility-agent',
  },
  {
    slug: 'research-synthesiser',
    href: '/agents/research-synthesiser',
    planKey: 'business',
  },
  {
    slug: 'retrenchment-navigator',
    href: '/agents/retrenchment-navigator',
    planKey: 'free',
    badgeKey: 'new',
  },
  {
    slug: 'property-concierge',
    href: '/agents/property-concierge',
    planKey: 'free',
    badgeKey: 'new',
  },
  {
    slug: 'sme-compliance-navigator',
    href: '/agents/sme-compliance-navigator',
    planKey: 'free',
  },
  {
    slug: 'grant-draft-generator',
    href: '/agents/grant-draft-generator',
    planKey: 'free',
  },
  {
    slug: 'deadline-monitor',
    href: '/agents/deadline-monitor',
    planKey: 'pro',
  },
  {
    slug: 'welfare-eligibility',
    href: '/agents/welfare-eligibility',
    planKey: 'free',
    badgeKey: 'new',
    backendName: 'welfare-eligibility-agent',
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

/** Reverse-lookup from a backend agent_runs.agent_name value (e.g.
 * "eligibility-agent") to the frontend slug/href (e.g. "grant-finder") —
 * needed by the agent-run history list, which only has the backend name
 * to work with. Falls back to treating the name as already-a-slug when no
 * WIRED_AGENTS entry overrides it (true for every agent except
 * grant-finder today). */
export function agentSlugFromBackendName(backendName: string): string {
  const match = WIRED_AGENTS.find((a) => a.backendName === backendName);
  return match?.slug ?? backendName;
}
