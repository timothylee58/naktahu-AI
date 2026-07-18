'use client';

import { useState } from 'react';
import Link from 'next/link';
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
    <main className="min-h-screen bg-zinc-50">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/90 backdrop-blur px-4 py-3 flex gap-3 items-center">
        <Link href="/agents" className="text-sm text-blue-600 hover:underline">← Agents</Link>
        <h1 className="font-bold text-zinc-900">Health Triage</h1>
        <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">Percuma</span>
      </header>

      <div className="max-w-2xl mx-auto p-4 flex flex-col gap-5">
        {/* Emergency disclaimer */}
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <span className="text-lg" aria-hidden>⚠️</span>
          <p className="text-xs text-amber-800 leading-relaxed">
            Bukan diagnosis perubatan. Untuk kecemasan, hubungi <strong>999</strong> segera.
            Alat sivik percuma ini hanya memberi panduan am.
          </p>
        </div>

        {/* Symptom selector */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-5 flex flex-col gap-4">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">Pilih simptom anda</h2>
            <p className="text-xs text-zinc-500 mt-0.5">Tekan untuk memilih (boleh pilih banyak)</p>
          </div>
          <ChipSelector
            options={SYMPTOM_OPTIONS}
            selected={selectedSymptoms}
            onToggle={toggleSymptom}
            multiple
          />
        </section>

        {/* Duration selector */}
        {selectedSymptoms.length > 0 && (
          <section className="rounded-2xl border border-zinc-200 bg-white p-5 flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-zinc-900">Berapa lama?</h2>
            <ChipSelector
              options={DURATION_OPTIONS}
              selected={duration}
              onToggle={toggleDuration}
              multiple={false}
              size="sm"
            />
          </section>
        )}

        {/* Extra details */}
        {selectedSymptoms.length > 0 && (
          <section className="rounded-2xl border border-zinc-200 bg-white p-5 flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-zinc-900">Maklumat tambahan (pilihan)</h2>
            <textarea
              className="w-full rounded-xl border border-zinc-200 p-3 text-sm placeholder:text-zinc-400 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-100"
              rows={2}
              value={extraDetails}
              onChange={(e) => setExtraDetails(e.target.value)}
              placeholder="Cth: Ada alahan ubat, sedang mengandung, dll."
            />
            <button
              type="button"
              disabled={loading || selectedSymptoms.length === 0}
              onClick={() => void submit()}
              className="self-end px-5 py-2.5 bg-red-600 text-white rounded-xl text-sm font-semibold disabled:opacity-50 transition-colors hover:bg-red-700"
            >
              {loading ? 'Memeriksa…' : 'Dapatkan panduan'}
            </button>
          </section>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Loading state */}
        {loading && <AgentLoadingSkeleton message="Menganalisis simptom anda…" />}

        {/* Results */}
        {output && !loading && (
          <div className="flex flex-col gap-4">
            {/* Urgency card */}
            <section className={`rounded-2xl border ${urgencyStyle.border} ${urgencyStyle.bg} p-5`}>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl" aria-hidden>{urgencyStyle.icon}</span>
                <h2 className={`text-sm font-bold ${urgencyStyle.textColor}`}>{urgencyStyle.label}</h2>
              </div>
              <p className="text-sm text-zinc-700 leading-relaxed">
                {String(output.facility_recommendation ?? '')}
              </p>
            </section>

            {/* Facility cards */}
            {facilities.length > 0 && (
              <section className="rounded-2xl border border-zinc-200 bg-white p-5 flex flex-col gap-3">
                <h2 className="text-sm font-semibold text-zinc-900 flex items-center gap-2">
                  <span aria-hidden>🏥</span> Kemudahan berdekatan
                </h2>
                <ul className="space-y-3">
                  {facilities.map((f, i) => (
                    <li key={i} className="flex items-start gap-3 rounded-xl border border-zinc-100 bg-zinc-50 p-3">
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600 text-sm">
                        🏥
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-zinc-900">{f.name ?? f.type ?? 'Kemudahan'}</p>
                        {f.action && <p className="text-xs text-zinc-500 mt-0.5">{f.action}</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Self-care tips */}
            {output.self_care && (
              <section className="rounded-2xl border border-zinc-200 bg-white p-5">
                <h2 className="text-sm font-semibold text-zinc-900 mb-2 flex items-center gap-2">
                  <span aria-hidden>⚕️</span> Penjagaan di rumah
                </h2>
                <p className="text-sm text-zinc-600 leading-relaxed">{String(output.self_care)}</p>
              </section>
            )}

            {/* Disclaimer */}
            <div className="rounded-xl border border-amber-100 bg-amber-50/50 px-4 py-3">
              <p className="text-xs text-amber-700">
                {String(output.disclaimer ?? 'Ini adalah panduan am sahaja. Sila berjumpa doktor untuk diagnosis yang tepat.')}
              </p>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
