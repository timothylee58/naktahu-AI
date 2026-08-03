'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { useI18n } from '@/lib/i18n';

const SYMPTOM_OPTIONS: ChipOption[] = [
  { id: 'demam', label: 'Demam', icon: '🤒' },
  { id: 'batuk', label: 'Batuk', icon: '😷' },
  { id: 'sakit_kepala', label: 'Sakit kepala', icon: '🤕' },
  { id: 'loya', label: 'Loya / Muntah', icon: '🤢' },
  { id: 'sesak_nafas', label: 'Sesak nafas', icon: '💨' },
  { id: 'sakit_perut', label: 'Sakit perut', icon: '🤧' },
  { id: 'cirit_birit', label: 'Cirit-birit', icon: '💧' },
  { id: 'sakit_dada', label: 'Sakit dada', icon: '💔' },
  { id: 'ruam', label: 'Ruam kulit', icon: '🔴' },
  { id: 'pening', label: 'Pening', icon: '😵' },
];

const DURATION_OPTIONS: ChipOption[] = [
  { id: 'less_1', label: '< 1 hari' },
  { id: '1_3', label: '1–3 hari' },
  { id: '3_7', label: '3–7 hari' },
  { id: 'more_7', label: '> 1 minggu' },
];

type UrgencyLevel = 'emergency' | 'moderate' | 'mild' | 'unknown';

function getUrgencyLevel(output: Record<string, unknown>): UrgencyLevel {
  const rec = String(output.facility_recommendation ?? '').toLowerCase();
  if (rec.includes('999') || rec.includes('kecemasan') || rec.includes('emergency')) return 'emergency';
  if (rec.includes('klinik') || rec.includes('today') || rec.includes('hari ini')) return 'moderate';
  if (rec.includes('pantau') || rec.includes('monitor') || rec.includes('rest')) return 'mild';
  return 'moderate';
}

const URGENCY_STYLES: Record<UrgencyLevel, { bg: string; border: string; icon: string; label: string; textColor: string }> = {
  emergency: { bg: 'bg-red-50', border: 'border-red-200', icon: '🔴', label: 'Kecemasan — Pergi hospital segera', textColor: 'text-red-800' },
  moderate: { bg: 'bg-amber-50', border: 'border-amber-200', icon: '🟡', label: 'Sederhana — Lawati klinik hari ini', textColor: 'text-amber-800' },
  mild: { bg: 'bg-green-50', border: 'border-green-200', icon: '🟢', label: 'Ringan — Pantau di rumah', textColor: 'text-green-800' },
  unknown: { bg: 'bg-zinc-50', border: 'border-zinc-200', icon: '⚪', label: 'Sila dapatkan nasihat', textColor: 'text-zinc-800' },
};

export default function HealthTriagePage() {
  const { t } = useI18n();
  const { start } = useAgentApi();
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [duration, setDuration] = useState<string[]>([]);
  const [extraDetails, setExtraDetails] = useState('');
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleSymptom = (id: string) => {
    setSelectedSymptoms((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  };

  const toggleDuration = (id: string) => {
    setDuration([id]);
  };

  const buildMessage = (): string => {
    const symptomLabels = selectedSymptoms
      .map((id) => SYMPTOM_OPTIONS.find((o) => o.id === id)?.label ?? id)
      .join(', ');
    const dur = DURATION_OPTIONS.find((o) => o.id === duration[0])?.label ?? '';
    let msg = symptomLabels;
    if (dur) msg += ` sejak ${dur}`;
    if (extraDetails.trim()) msg += `. ${extraDetails.trim()}`;
    return msg;
  };

  const submit = async () => {
    if (selectedSymptoms.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await start('health-triage', { message: buildMessage(), language: 'bm' });
      setOutput((res.output as Record<string, unknown>) ?? res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ralat berlaku');
    } finally {
      setLoading(false);
    }
  };

  const facilities = (output?.facilities as Array<Record<string, string>>) ?? [];
  const urgency = output ? getUrgencyLevel(output) : 'unknown';
  const urgencyStyle = URGENCY_STYLES[urgency];

  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="bg-white/80 backdrop-blur-md supports-[backdrop-filter]:bg-white/70 border-b border-zinc-100 px-4 py-3 flex gap-3 items-center sticky top-0 z-10 dark:bg-[#0A0F1E]/80 dark:border-white/10">
        <Link href="/agents" className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 transition-colors dark:text-blue-400 dark:hover:text-blue-300">
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Agents
        </Link>
        <h1 className="font-bold tracking-tight">Health Triage</h1>
      </header>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        <p className="text-xs text-zinc-500 leading-relaxed dark:text-zinc-400">Free civic tool — not a medical diagnosis. For emergencies call 999.</p>
        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          <ChipSelector options={SYMPTOM_OPTIONS} selected={selectedSymptoms} onToggle={toggleSymptom} />
          <ChipSelector options={DURATION_OPTIONS} selected={duration} onToggle={toggleDuration} multiple={false} size="sm" />
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={2}
            value={extraDetails}
            onChange={(e) => setExtraDetails(e.target.value)}
            placeholder="Butiran tambahan (pilihan)"
          />
          <button
            type="button"
            disabled={loading || selectedSymptoms.length === 0}
            onClick={() => void submit()}
            className="self-end px-4 py-2 bg-red-600 hover:bg-red-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-red-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? 'Checking…' : 'Get guidance'}
          </button>
          {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
        </section>
        {output && (
          <section className="bg-white border border-red-100 rounded-2xl p-4 text-sm shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-red-500/30">
            <p className="font-medium">{String(output.facility_recommendation)}</p>
            <ul className="mt-2 space-y-1">{facilities.map((f) => <li key={f.type} className="text-zinc-600 dark:text-zinc-400">{f.name} — {f.action}</li>)}</ul>
            <p className="mt-3 text-xs text-amber-800 dark:text-amber-300">{String(output.disclaimer)}</p>
          </section>
        )}
      </motion.div>
    </main>
  );
}
