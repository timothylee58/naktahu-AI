'use client';

/**
 * Lightweight in-content title for individual agent pages. The sidebar +
 * top app-bar (with the hamburger and NakTahu logo) now live once in
 * apps/agents/layout.tsx — this just labels the page inside that shell,
 * replacing the old per-page "← Agents / Title" sticky header + back-link.
 */
export function AgentPageHeader({ title, badge }: { title: string; badge?: string }) {
  return (
    <div className="flex items-center gap-2 px-4 pt-4 sm:px-6">
      <h1 className="text-lg font-bold tracking-tight">{title}</h1>
      {badge && (
        <span className="text-xs bg-nk-official/20 text-nk-official-dim px-2 py-0.5 rounded-full font-semibold dark:bg-nk-official/15 dark:text-nk-official">
          {badge}
        </span>
      )}
    </div>
  );
}
