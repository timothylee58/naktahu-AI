import type { Citation } from '@/lib/types';

export interface SourceRow {
  url: string;
  host: string;
  ministry: string;
  tier: 'official' | 'community' | null;
}

function parseHttpUrl(url: string | undefined): URL | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === 'http:' || u.protocol === 'https:' ? u : null;
  } catch {
    return null;
  }
}

/** One row per distinct source URL. A citation without a real http(s) URL is
 * dropped rather than shown with an invented link. */
export function sourceRows(citations: Citation[]): SourceRow[] {
  const seen = new Set<string>();
  const rows: SourceRow[] = [];
  for (const c of citations) {
    const url = c.url ?? c.source_url;
    const parsed = parseHttpUrl(url);
    if (!url || !parsed || seen.has(url)) continue;
    seen.add(url);
    rows.push({
      url,
      host: parsed.hostname.replace(/^www\./, ''),
      ministry: c.ministry,
      tier: c.source_tier === 'official' || c.source_tier === 'community' ? c.source_tier : null,
    });
  }
  return rows;
}

/** The header-level "Official source" badge: only when EVERY listed source is
 * known-official. Mixed or unknown tiers get per-row badges only. */
export function allOfficial(rows: SourceRow[]): boolean {
  return rows.length > 0 && rows.every((r) => r.tier === 'official');
}

/** Most recent retrieved_at across the citations, or null if none is a valid
 * timestamp. Never falls back to "now". */
export function latestChecked(citations: Citation[]): Date | null {
  let latest: Date | null = null;
  for (const c of citations) {
    if (!c.retrieved_at) continue;
    const d = new Date(c.retrieved_at);
    if (Number.isNaN(d.getTime())) continue;
    if (!latest || d > latest) latest = d;
  }
  return latest;
}

export function formatCheckedDate(date: Date, locale: string): string {
  const tag = locale === 'zh' ? 'zh-CN' : locale === 'ms' ? 'ms-MY' : 'en-MY';
  return date.toLocaleDateString(tag, { year: 'numeric', month: 'short', day: 'numeric' });
}
