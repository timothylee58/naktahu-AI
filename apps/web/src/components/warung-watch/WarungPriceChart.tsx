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

// Different check-ins can report different menu items for the same warung
// (no single canonical "the price" — see 033_warung_checkin_price.sql's
// module comment), so a naive single line across every priced check-in
// would connect e.g. a Nasi Lemak price to a Teh Tarik price and imply a
// price change that never happened (confirmed CodeRabbit finding). Rather
// than a multi-series chart (needs a legend/color per item, and with a
// small crowdsourced sample most items would only have 1-2 points each,
// not enough to chart anyway), this restricts the chart to whichever
// single item has been reported most often, and names that item in the
// heading so it's clear what's being charted.
function mostReportedItem(history: PriceHistoryPoint[]): string {
  const counts = new Map<string, number>();
  for (const h of history) {
    counts.set(h.price_item, (counts.get(h.price_item) ?? 0) + 1);
  }
  let best = history[0].price_item;
  let bestCount = 0;
  for (const h of history) {
    const count = counts.get(h.price_item) ?? 0;
    if (count > bestCount) {
      bestCount = count;
      best = h.price_item;
    }
  }
  return best;
}

// Below a minimum point count a line chart is genuinely misleading (a
// "trend" drawn through 1-2 points implies more signal than exists), so
// this shows an honest "not enough reports yet" state instead of a chart
// with 1 dot. Checked against the single-item series, not the overall
// history — 5 reports split across 3 different items isn't 5 points of
// signal for any one item's trend.
const MIN_POINTS_FOR_CHART = 3;

export function WarungPriceChart({ history, isDark = true }: WarungPriceChartProps) {
  const { t } = useI18n();
  const mutedText = isDark ? 'text-zinc-400' : 'text-zinc-500';
  const gridColor = isDark ? 'rgba(255,255,255,0.1)' : '#e4e4e7';
  const axisTick = { fontSize: 11, fill: isDark ? '#a1a1aa' : '#71717a' };

  if (history.length === 0) {
    return null;
  }

  const item = mostReportedItem(history);
  const itemHistory = history.filter((h) => h.price_item === item);

  if (itemHistory.length < MIN_POINTS_FOR_CHART) {
    return (
      <p className={`text-xs ${mutedText}`}>
        {t('warung_watch.price_chart_not_enough').replace('{n}', String(itemHistory.length))}
      </p>
    );
  }

  const chartData = itemHistory.map((h) => ({
    date: formatDate(h.created_at),
    price: h.price_myr,
  }));

  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {t('warung_watch.price_chart_title').replace('{item}', item)}
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
              formatter={(value: number) => [`RM${value.toFixed(2)}`, item]}
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
