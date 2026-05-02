import Link from 'next/link';
import { TypewriterQueryWrapper } from '@/components/landing/TypewriterQueryWrapper';
import { LandingFeatures } from '@/components/landing/LandingFeatures';

export default function LandingPage() {
  const domains = [
    { key: 'tax', label: 'Cukai & LHDN', en: 'Tax & LHDN' },
    { key: 'epf', label: 'KWSP / EPF', en: 'EPF / KWSP' },
    { key: 'business', label: 'Perniagaan & SSM', en: 'Business & SSM' },
    { key: 'education', label: 'Pendidikan & SPM', en: 'Education & SPM' },
    { key: 'health', label: 'Kesihatan', en: 'Healthcare' },
    { key: 'immigration', label: 'Imigresen', en: 'Immigration' },
  ];

  return (
    <div className="flex flex-col min-h-screen bg-[#0A0F1E] text-white font-sans">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-white/10">
        <span className="text-lg font-bold tracking-tight">NakTahu</span>
        <Link
          href="/chat"
          className="text-sm font-semibold bg-[#2563EB] hover:bg-blue-500 transition-colors px-4 py-2 rounded-full"
        >
          Mula Bertanya
        </Link>
      </nav>

      {/* Hero */}
      <section className="flex flex-col items-center justify-center flex-1 text-center px-6 py-24 gap-8">
        <div className="inline-flex items-center gap-2 text-xs font-semibold tracking-widest text-[#2563EB] uppercase border border-[#2563EB]/30 rounded-full px-4 py-1.5">
          🇲🇾 Dibuat untuk Malaysia
        </div>

        <h1 className="text-4xl sm:text-6xl font-bold leading-tight max-w-3xl tracking-tight">
          Tanya apa sahaja{' '}
          <span className="text-[#2563EB]">tentang Malaysia.</span>
        </h1>

        <p className="text-lg text-zinc-400 max-w-xl leading-relaxed">
          NakTahu AI memberi jawapan berdasarkan sumber rasmi kerajaan —
          dalam Bahasa Malaysia atau Inggeris.
        </p>

        {/* Animated search bar */}
        <div className="w-full max-w-xl bg-white/5 border border-white/10 rounded-2xl px-5 py-4 flex items-center gap-3">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5 text-zinc-500 flex-shrink-0"
          >
            <path
              fillRule="evenodd"
              d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z"
              clipRule="evenodd"
            />
          </svg>
          <TypewriterQueryWrapper />
        </div>

        <Link
          href="/chat"
          className="inline-flex items-center gap-2 bg-[#2563EB] hover:bg-blue-500 transition-colors text-white font-semibold px-8 py-3.5 rounded-full text-base shadow-lg shadow-blue-900/40"
        >
          Mula Bertanya
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5"
          >
            <path
              fillRule="evenodd"
              d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10Z"
              clipRule="evenodd"
            />
          </svg>
        </Link>
      </section>

      {/* Features */}
      <section className="px-6 py-20 border-t border-white/10">
        <h2 className="text-center text-2xl font-bold mb-12 text-zinc-200">
          Kenapa NakTahu?
        </h2>
        <LandingFeatures />
      </section>

      {/* Domains */}
      <section className="px-6 py-16 border-t border-white/10 flex flex-col items-center gap-6">
        <h2 className="text-2xl font-bold text-zinc-200">Domain Pengetahuan</h2>
        <div className="flex flex-wrap justify-center gap-3 max-w-2xl">
          {domains.map((d) => (
            <span
              key={d.key}
              className="border border-[#2563EB]/40 text-[#2563EB] rounded-full px-4 py-1.5 text-sm font-medium bg-[#2563EB]/10"
            >
              {d.label}
            </span>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-zinc-500">
        <div className="flex flex-col gap-1">
          <span className="font-semibold text-zinc-300">NakTahu AI</span>
          <span>Maklumat kerajaan, dalam genggaman anda.</span>
        </div>
        <div className="flex flex-col items-end gap-1 text-right">
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors"
          >
            GitHub ↗
          </a>
          <span className="text-xs max-w-xs text-right">
            NakTahu AI adalah projek portfolio. Bukan nasihat rasmi kerajaan.
          </span>
        </div>
      </footer>
    </div>
  );
}
