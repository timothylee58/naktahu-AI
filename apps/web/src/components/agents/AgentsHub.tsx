'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  FlaskConical,
  GraduationCap,
  HeartPulse,
  Landmark,
  Plane,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useI18n } from '@/lib/i18n';
import {
  WIRED_AGENTS,
  agentDescKey,
  agentPlanKey,
  agentTitleKey,
  type AgentPlanKey,
} from '@/lib/agents';

/** Per-agent icon + accent tile. Slugs match lib/agents.ts / the API registry. */
const AGENT_VISUALS: Record<string, { icon: LucideIcon; tile: string }> = {
  'compliance-drafter': {
    icon: FileText,
    tile: 'bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300',
  },
  'study-agent': {
    icon: GraduationCap,
    tile: 'bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300',
  },
  'immigration-navigator': {
    icon: Plane,
    tile: 'bg-sky-50 text-sky-600 dark:bg-sky-500/15 dark:text-sky-300',
  },
  'health-triage': {
    icon: HeartPulse,
    tile: 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300',
  },
  'grant-finder': {
    icon: Landmark,
    tile: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300',
  },
  'research-synthesiser': {
    icon: FlaskConical,
    tile: 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300',
  },
};

const PLAN_BADGE_VARIANT: Record<AgentPlanKey, 'secondary' | 'default' | 'success'> = {
  free: 'success',
  free_plus: 'secondary',
  student: 'default',
  business: 'default',
};

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.1 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: 'easeOut' as const } },
};

export function AgentsHub() {
  const { t } = useI18n();

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-white/10 dark:bg-[#0A0F1E]/80">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3 sm:px-6">
          <Link
            href="/chat"
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 transition-colors hover:text-blue-500 dark:text-blue-400 locale-nowrap"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            {t('nav.home')}
          </Link>
          <span className="text-zinc-300 dark:text-white/20" aria-hidden>
            /
          </span>
          <h1 className="text-sm font-bold">{t('agents.hub.title')}</h1>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="mb-10 flex flex-col items-start gap-4"
        >
          <span className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-blue-600 dark:text-blue-400 locale-nowrap">
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            {t('agents.hub.title')}
          </span>
          <h2 className="max-w-2xl text-3xl font-bold leading-tight tracking-tight sm:text-4xl locale-text-balance">
            {t('agents.hub.subtitle')}
          </h2>
        </motion.div>

        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid gap-4 sm:grid-cols-2"
        >
          {WIRED_AGENTS.map((agent) => {
            const visual = AGENT_VISUALS[agent.slug] ?? {
              icon: Sparkles,
              tile: 'bg-zinc-100 text-zinc-600 dark:bg-white/10 dark:text-zinc-300',
            };
            const Icon = visual.icon;
            return (
              <motion.div key={agent.slug} variants={item} whileHover={{ y: -4 }}>
                <Link href={agent.href} className="group block h-full">
                  <Card className="h-full border-zinc-200 transition-shadow hover:shadow-md dark:border-white/10 dark:bg-white/5 dark:text-white dark:hover:border-white/20">
                    <CardHeader className="h-full gap-3 space-y-0">
                      <div className="flex items-start justify-between gap-3">
                        <div
                          className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl ${visual.tile}`}
                        >
                          <Icon className="h-5 w-5" aria-hidden />
                        </div>
                        <div className="flex items-center gap-1.5">
                          {agent.badgeKey ? (
                            <Badge>{t(`agents.badge.${agent.badgeKey}`)}</Badge>
                          ) : null}
                          <Badge variant={PLAN_BADGE_VARIANT[agent.planKey]}>
                            {t(agentPlanKey(agent.planKey))}
                          </Badge>
                        </div>
                      </div>
                      <CardTitle className="text-base">{t(agentTitleKey(agent.slug))}</CardTitle>
                      <CardDescription className="leading-relaxed dark:text-zinc-400">
                        {t(agentDescKey(agent.slug))}
                      </CardDescription>
                      <span className="mt-auto inline-flex items-center gap-1 pt-1 text-sm font-semibold text-blue-600 dark:text-blue-400 locale-nowrap">
                        {t('agents.hub.open')}
                        <ArrowRight
                          className="h-4 w-4 transition-transform group-hover:translate-x-1"
                          aria-hidden
                        />
                      </span>
                    </CardHeader>
                  </Card>
                </Link>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </main>
  );
}
