'use client';

import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

const ROWS = [
  { labelKey: 'landing.compare.row.sources', usKey: 'landing.compare.row.sources.us', themKey: 'landing.compare.row.sources.them' },
  { labelKey: 'landing.compare.row.languages', usKey: 'landing.compare.row.languages.us', themKey: 'landing.compare.row.languages.them' },
  { labelKey: 'landing.compare.row.domains', usKey: 'landing.compare.row.domains.us', themKey: 'landing.compare.row.domains.them' },
  { labelKey: 'landing.compare.row.confidence', usKey: 'landing.compare.row.confidence.us', themKey: 'landing.compare.row.confidence.them' },
] as const;

interface ComparisonSectionProps {
  isDark?: boolean;
}

export function ComparisonSection({ isDark = true }: ComparisonSectionProps) {
  const { t } = useI18n();
  const borderClass = isDark ? 'border-white/10' : 'border-zinc-200';
  const rowLabelClass = isDark ? 'text-zinc-300' : 'text-zinc-700';
  const usClass = isDark ? 'text-blue-300' : 'text-blue-700';
  const themClass = isDark ? 'text-zinc-500' : 'text-zinc-400';
  const headerUsClass = isDark ? 'text-blue-400 bg-blue-500/10' : 'text-blue-700 bg-blue-50';
  const headerThemClass = isDark ? 'text-zinc-400' : 'text-zinc-500';

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5 }}
      className={`max-w-3xl mx-auto w-full overflow-x-auto rounded-2xl border ${borderClass}`}
    >
      <table className="w-full text-sm min-w-[480px]">
        <thead>
          <tr className={`border-b ${borderClass}`}>
            <th className="text-left font-medium py-3 px-4 w-1/3" />
            <th className={`text-left font-bold py-3 px-4 rounded-t-lg locale-nowrap ${headerUsClass}`}>
              {t('landing.compare.us')}
            </th>
            <th className={`text-left font-medium py-3 px-4 locale-nowrap ${headerThemClass}`}>
              {t('landing.compare.them')}
            </th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row, i) => (
            <tr key={row.labelKey} className={i < ROWS.length - 1 ? `border-b ${borderClass}` : undefined}>
              <td className={`py-3 px-4 font-medium locale-text-balance ${rowLabelClass}`}>{t(row.labelKey)}</td>
              <td className={`py-3 px-4 locale-text-balance ${usClass}`}>
                <span aria-hidden className="mr-1.5">✅</span>
                {t(row.usKey)}
              </td>
              <td className={`py-3 px-4 locale-text-balance ${themClass}`}>
                <span aria-hidden className="mr-1.5">⚠️</span>
                {t(row.themKey)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </motion.div>
  );
}
