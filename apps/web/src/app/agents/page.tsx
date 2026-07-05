'use client';

import Link from 'next/link';
import { useI18n } from '@/lib/i18n';

const AGENTS = [
  {
    slug: 'compliance-drafter',
    title: 'Compliance Drafter',
    desc: 'Multi-domain PDF report with HITL review. 1 credit (Business unlimited).',
    plan: 'Free+',
    href: '/agents/compliance-drafter',
  },
  {
    slug: 'study-agent',
    title: 'Study Agent',
    desc: 'Upload SPM past papers — extract questions, RAG explanations, topic tracking.',
    plan: 'Student',
    href: '/agents/study-agent',
  },
  {
    slug: 'immigration-navigator',
    title: 'Immigration Navigator',
    desc: '3–5 turn visa intake → checklist, warnings, expiry-aware citations. 1 credit.',
    plan: 'Free+',
    href: '/agents/immigration-navigator',
  },
  {
    slug: 'health-triage',
    title: 'Health Triage',
    desc: 'BM symptom intake → KKM guidance → clinic/hospital recommendation. Free civic tool.',
    plan: 'Free',
    href: '/agents/health-triage',
  },
  {
    slug: 'grant-finder',
    title: 'Grant Finder',
    desc: 'Recommended — match your profile to government grants (MDEC, TEKUN, MARA, etc.).',
    plan: 'Free',
    href: '/agents/grant-finder',
    badge: 'New',
  },
  {
    slug: 'research-synthesiser',
    title: 'Research Synthesiser',
    desc: 'Parallel fan-out across 3 RAG domains with deduplicated citations. Business/API tier.',
    plan: 'Business',
    href: '/agents/research-synthesiser',
  },
];

export default function AgentsHubPage() {
  const { t } = useI18n();

  return (
    <main className="min-h-screen bg-zinc-50">
      <header className="bg-white border-b border-zinc-200 px-4 py-3 flex items-center gap-3">
        <Link href="/chat" className="text-sm text-blue-600 hover:underline">← {t('nav.home')}</Link>
        <h1 className="text-lg font-bold text-zinc-900">NakTahu Agents</h1>
      </header>
      <div className="max-w-3xl mx-auto px-4 py-8 grid gap-4">
        <p className="text-sm text-zinc-600">
          LangGraph-powered agents with official-source RAG, plan gating, and credit metering.
        </p>
        {AGENTS.map((a) => (
          <Link
            key={a.slug}
            href={a.href}
            className="block bg-white border border-zinc-200 rounded-2xl p-5 hover:border-blue-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-semibold text-zinc-900">{a.title}</h2>
              <span className="text-[10px] font-bold uppercase tracking-wide text-zinc-500 bg-zinc-100 px-2 py-0.5 rounded-full">
                {a.plan}
              </span>
            </div>
            <p className="text-sm text-zinc-600 mt-1">{a.desc}</p>
            {'badge' in a && a.badge && (
              <span className="inline-block mt-2 text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
                {a.badge}
              </span>
            )}
          </Link>
        ))}
      </div>
    </main>
  );
}
