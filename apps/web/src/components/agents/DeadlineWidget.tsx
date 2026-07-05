'use client';

import useSWR from 'swr';

interface DeadlineEntry {
  id: string;
  domain: string;
  deadline_name: string;
  due_date: string;
  recurrence?: string;
  source_url: string;
}

interface DeadlineWidgetProps {
  accessToken: string | null;
  variant?: 'light' | 'dark';
}

function daysUntil(isoDate: string): number {
  const due = new Date(isoDate);
  const now = new Date();
  due.setHours(0, 0, 0, 0);
  now.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - now.getTime()) / 86_400_000);
}

export function DeadlineWidget({ accessToken, variant = 'light' }: DeadlineWidgetProps) {
  const isDark = variant === 'dark';
  const { data: deadlines = [], isLoading } = useSWR<DeadlineEntry[]>(
    accessToken ? 'deadline-widget' : null,
    () =>
      fetch('/api/v1/agents/deadline-monitor/deadlines', {
        headers: { Authorization: `Bearer ${accessToken}` },
      }).then((r) => {
        if (!r.ok) throw new Error('deadlines');
        return r.json() as Promise<DeadlineEntry[]>;
      }),
    { revalidateOnFocus: false },
  );

  if (!accessToken) return null;

  const upcoming = deadlines
    .map((d) => ({ ...d, days: daysUntil(d.due_date) }))
    .filter((d) => d.days >= 0 && d.days <= 30)
    .sort((a, b) => a.days - b.days)
    .slice(0, 5);

  if (isLoading || upcoming.length === 0) return null;

  return (
    <div
      className={`mx-2 mb-3 rounded-xl border p-3 flex flex-col gap-2 ${
        isDark ? 'border-white/10 bg-white/5' : 'border-amber-200 bg-amber-50/80'
      }`}
    >
      <span
        className={`text-[11px] font-semibold uppercase tracking-wider px-1 locale-nowrap ${
          isDark ? 'text-amber-300' : 'text-amber-800'
        }`}
      >
        Deadline Monitor
      </span>
      <ul className="flex flex-col gap-1.5">
        {upcoming.map((d) => (
          <li key={d.id} className="text-xs">
            <a
              href={d.source_url}
              target="_blank"
              rel="noreferrer"
              className={isDark ? 'text-zinc-200 hover:text-white' : 'text-zinc-800 hover:text-blue-700'}
            >
              {d.deadline_name}
            </a>
            <span className={`ml-1 ${isDark ? 'text-zinc-500' : 'text-amber-700'}`}>
              · {d.days === 0 ? 'Today' : `${d.days}d`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
