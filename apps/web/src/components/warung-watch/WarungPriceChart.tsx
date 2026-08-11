'use client';

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useI18n } from '@/lib/i18n';

export interface PriceHistoryPoint {
  price_item: string;
  price_myr: number;
  created_at: string;
}

interface WarungPriceChartProps {
  history: PriceHistoryPoint[];
  isDark?: boolean;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// Renders the real, crowdsourced price-report series from
// GET /api/v1/warung-watch/price-history — never fabricated sample data
// (see 033_warung_checkin_price.sql's module comment). Below a minimum
// point count a line chart is genuinely misleading (a "trend" drawn
// through 1-2 points implies more signal than exists), so this shows an
// honest "not enough reports yet" state instead of a chart with 1 dot.
const MIN_POINTS_FOR_CHART = 3;

export function WarungPriceChart({ history, isDark = true }: WarungPriceChartProps) {
  const { t } = useI18n();
  const mutedText = isDark ? 'text-zinc-400' : 'text-zinc-500';
  const gridColor = isDark ? 'rgba(255,255,255,0.1)' : '#e4e4e7';
  const axisTick = { fontSize: 11, fill: isDark ? '#a1a1aa' : '#71717a' };

  if (history.length === 0) {
    return null;
  }

  if (history.length < MIN_POINTS_FOR_CHART) {
    return (
      <p className={`text-xs ${mutedText}`}>
        {t('warung_watch.price_chart_not_enough').replace('{n}', String(history.length))}
      </p>
    );
  }

  // Recharts needs numeric x-axis-friendly data; keep price_item for the
  // tooltip label since different check-ins can report different items
  // (see the migration's reasoning for why there's no single "the price").
  const chartData = history.map((h) => ({
    date: formatDate(h.created_at),
    price: h.price_myr,
    item: h.price_item,
  }));

  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {t('warung_watch.price_chart_title')}
      </h3>
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="date" tick={axisTick} />
            <YAxis
              tick={axisTick}
              tickFormatter={(v) => `RM${v}`}
              width={48}
            />
            <Tooltip
              formatter={(value: number, _name, props) => [`RM${value.toFixed(2)}`, props.payload.item]}
              contentStyle={
                isDark
                  ? { background: '#111827', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }
                  : { fontSize: 12 }
              }
            />
            <Line type="monotone" dataKey="price" stroke="#ea580c" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
