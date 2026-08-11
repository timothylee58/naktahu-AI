/**
 * Rule-based "which agent / which API should I use" suggestion engine.
 *
 * Deliberately NOT an LLM call — a static keyword→suggestion table matched
 * client-side. Zero extra latency/cost per lookup, and easy to extend by
 * just adding a row. If this ever needs to handle genuinely ambiguous
 * free-text intent better than keyword matching can, that's a real
 * architecture decision (a new Haiku tool-call classifier, same class of
 * change flagged for Warung Watch's own tool call) — not something to
 * silently upgrade to from here.
 */

export interface AgentSuggestion {
  kind: 'agent';
  slug: string;
  href: string;
  titleKey: string;
  descKey: string;
}

export interface ApiSuggestion {
  kind: 'api';
  endpoint: string;
  method: 'GET' | 'POST';
  labelKey: string;
  docsHref: string;
}

export type Suggestion = AgentSuggestion | ApiSuggestion;

interface SuggestionRule {
  keywords: string[];
  suggestions: Suggestion[];
}

// Keep this in the query's language-agnostic form — keywords cover common
// BM/EN terms for the same intent so a query in either language matches.
const RULES: SuggestionRule[] = [
  {
    keywords: ['tax', 'cukai', 'lhdn', 'income tax', 'e-filing'],
    suggestions: [
      { kind: 'agent', slug: 'compliance-drafter', href: '/agents/compliance-drafter', titleKey: 'agents.compliance-drafter.title', descKey: 'agents.compliance-drafter.desc' },
      { kind: 'api', endpoint: '/api/v1/public/query', method: 'POST', labelKey: 'suggestions.api.query', docsHref: '/developer' },
    ],
  },
  {
    keywords: ['epf', 'kwsp', 'socso', 'perkeso', 'eis', 'retirement', 'pencen'],
    suggestions: [
      { kind: 'agent', slug: 'compliance-drafter', href: '/agents/compliance-drafter', titleKey: 'agents.compliance-drafter.title', descKey: 'agents.compliance-drafter.desc' },
      { kind: 'agent', slug: 'retrenchment-navigator', href: '/agents/retrenchment-navigator', titleKey: 'agents.retrenchment-navigator.title', descKey: 'agents.retrenchment-navigator.desc' },
    ],
  },
  {
    keywords: ['grant', 'geran', 'funding', 'dana', 'mdec', 'cradle', 'sme corp'],
    suggestions: [
      { kind: 'agent', slug: 'grant-finder', href: '/agents/grant-finder', titleKey: 'agents.grant-finder.title', descKey: 'agents.grant-finder.desc' },
      { kind: 'agent', slug: 'grant-draft-generator', href: '/agents/grant-draft-generator', titleKey: 'agents.grant-draft-generator.title', descKey: 'agents.grant-draft-generator.desc' },
    ],
  },
  {
    keywords: ['visa', 'passport', 'pasport', 'immigration', 'imigresen', 'work permit'],
    suggestions: [
      { kind: 'agent', slug: 'immigration-navigator', href: '/agents/immigration-navigator', titleKey: 'agents.immigration-navigator.title', descKey: 'agents.immigration-navigator.desc' },
    ],
  },
  {
    keywords: ['sick', 'sakit', 'symptom', 'gejala', 'clinic', 'klinik', 'hospital', 'demam', 'fever'],
    suggestions: [
      { kind: 'agent', slug: 'health-triage', href: '/agents/health-triage', titleKey: 'agents.health-triage.title', descKey: 'agents.health-triage.desc' },
    ],
  },
  {
    keywords: ['study', 'belajar', 'spm', 'exam', 'peperiksaan', 'past paper', 'kertas soalan'],
    suggestions: [
      { kind: 'agent', slug: 'study-agent', href: '/agents/study-agent', titleKey: 'agents.study-agent.title', descKey: 'agents.study-agent.desc' },
    ],
  },
  {
    keywords: ['compliance', 'pematuhan', 'ssm', 'business registration', 'sst', 'patuhi'],
    suggestions: [
      { kind: 'agent', slug: 'sme-compliance-navigator', href: '/agents/sme-compliance-navigator', titleKey: 'agents.sme-compliance-navigator.title', descKey: 'agents.sme-compliance-navigator.desc' },
    ],
  },
  {
    keywords: ['retrench', 'buang kerja', 'lay off', 'lay-off', 'termination', 'pemberhentian'],
    suggestions: [
      { kind: 'agent', slug: 'retrenchment-navigator', href: '/agents/retrenchment-navigator', titleKey: 'agents.retrenchment-navigator.title', descKey: 'agents.retrenchment-navigator.desc' },
    ],
  },
  {
    keywords: ['deadline', 'tarikh akhir', 'due date', 'filing date'],
    suggestions: [
      { kind: 'agent', slug: 'deadline-monitor', href: '/agents/deadline-monitor', titleKey: 'agents.deadline-monitor.title', descKey: 'agents.deadline-monitor.desc' },
    ],
  },
  {
    keywords: ['research', 'penyelidikan', 'compare', 'banding', 'analysis', 'analisis'],
    suggestions: [
      { kind: 'agent', slug: 'research-synthesiser', href: '/agents/research-synthesiser', titleKey: 'agents.research-synthesiser.title', descKey: 'agents.research-synthesiser.desc' },
    ],
  },
  {
    keywords: ['warung', 'kedai makan', 'busy', 'sibuk', 'packed', 'penuh', 'queue', 'beratur', 'restoran'],
    suggestions: [
      { kind: 'api', endpoint: '/api/v1/warung-watch/status', method: 'GET', labelKey: 'suggestions.api.warung_watch', docsHref: '/warung-watch' },
    ],
  },
  {
    keywords: ['api', 'integrate', 'integrasi', 'developer', 'sdk', 'endpoint', 'webhook'],
    suggestions: [
      { kind: 'api', endpoint: '/api/v1/public/query', method: 'POST', labelKey: 'suggestions.api.query', docsHref: '/developer' },
      { kind: 'api', endpoint: '/api/v1/public/query/stream', method: 'POST', labelKey: 'suggestions.api.stream', docsHref: '/developer' },
    ],
  },
];

const DEFAULT_SUGGESTION: Suggestion = {
  kind: 'api',
  endpoint: '/api/v1/public/query',
  method: 'POST',
  labelKey: 'suggestions.api.query',
  docsHref: '/developer',
};

/** Match free text against the keyword table. Case-insensitive substring
 * match on the raw query — good enough for a rule table this small, and
 * keeps this a pure, dependency-free function (easy to unit test).
 * Returns [] on no match — the DEFAULT_SUGGESTION fallback lives in
 * suggestForQuery below, not here, since a live-typing consumer (the chat
 * input's auto-routing banner) wants silence on a genuine non-match, not
 * "try the Developer API" surfacing on every keystroke of an ordinary
 * question. */
export function matchAgentRules(query: string): Suggestion[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return [];

  const matched: Suggestion[] = [];
  const seen = new Set<string>();

  for (const rule of RULES) {
    if (rule.keywords.some((kw) => normalized.includes(kw))) {
      for (const s of rule.suggestions) {
        const key = s.kind === 'agent' ? `agent:${s.slug}` : `api:${s.endpoint}`;
        if (!seen.has(key)) {
          seen.add(key);
          matched.push(s);
        }
      }
    }
  }

  return matched.slice(0, 4);
}

/** Same matching, but with the DEFAULT_SUGGESTION fallback applied — used
 * by the Profile page/popover, where showing *something* for any non-empty
 * query is the intended UX (a deliberate "ask me anything, here's how" nudge
 * rather than a live suggestion overlay). */
export function suggestForQuery(query: string): Suggestion[] {
  if (!query.trim()) return [];
  const matched = matchAgentRules(query);
  return matched.length > 0 ? matched : [DEFAULT_SUGGESTION];
}
