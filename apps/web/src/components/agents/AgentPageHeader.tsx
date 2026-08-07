'use client';

/**
 * Lightweight in-content title for individual agent pages. The sidebar +
 * top app-bar (with the hamburger and NakTahu logo) now live once in
 * apps/agents/layout.tsx — this just labels the page inside that shell,
 * replacing the old per-page "← Agents / Title" sticky header + back-link.
 */
export function AgentPageHeader({ title }: { title: string }) {
  return (
    <h1 className="text-lg font-bold tracking-tight px-4 pt-4 sm:px-6">{title}</h1>
  );
}
