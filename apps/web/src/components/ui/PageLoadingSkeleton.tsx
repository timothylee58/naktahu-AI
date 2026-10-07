/**
 * PageLoadingSkeleton - A lightweight loading skeleton for Next.js route transitions.
 *
 * Rendered by loading.tsx files to provide immediate visual feedback while
 * the destination page loads. Unlike the full PageLoadingScreen (3D animated
 * brand transition for the landing CTA), this is a simple shimmer skeleton
 * that matches the app shell layout: sticky header + content area with
 * placeholder cards/lines.
 *
 * Server component by default (no 'use client' needed).
 */

interface PageLoadingSkeletonProps {
  /** Number of card placeholders to show in the content area */
  cards?: number;
  /** Number of text line placeholders per card */
  lines?: number;
  /** Whether to show a sidebar placeholder (for pages with AppSidebar) */
  showSidebar?: boolean;
}

function SkeletonLine({ width }: { width: string }) {
  return (
    <div
      className={`h-3 rounded-md bg-zinc-200 dark:bg-white/10 animate-pulse ${width}`}
    />
  );
}

function SkeletonCard({ lines }: { lines: number }) {
  const lineWidths = ['w-full', 'w-3/4', 'w-5/6', 'w-2/3', 'w-4/5'];
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-white/10 bg-white dark:bg-white/5 p-5 space-y-3">
      <div className="h-4 w-2/5 rounded-md bg-zinc-200 dark:bg-white/10 animate-pulse" />
      <div className="space-y-2.5 pt-1">
        {Array.from({ length: lines }, (_, i) => (
          <SkeletonLine key={i} width={lineWidths[i % lineWidths.length]} />
        ))}
      </div>
    </div>
  );
}

function SidebarSkeleton() {
  return (
    <div className="hidden lg:flex flex-col w-64 flex-shrink-0 border-r border-zinc-200 dark:border-white/10 bg-white dark:bg-[#12151C] p-4 gap-4">
      {/* Logo placeholder */}
      <div className="h-6 w-28 rounded-md bg-zinc-200 dark:bg-white/10 animate-pulse" />
      {/* Nav items */}
      <div className="mt-4 space-y-3">
        {Array.from({ length: 5 }, (_, i) => (
          <div
            key={i}
            className="h-8 rounded-lg bg-zinc-100 dark:bg-white/5 animate-pulse"
          />
        ))}
      </div>
    </div>
  );
}

export function PageLoadingSkeleton({
  cards = 3,
  lines = 3,
  showSidebar = true,
}: PageLoadingSkeletonProps) {
  return (
    <div className="flex h-full min-h-screen bg-zinc-50 dark:bg-[#12151C]">
      {showSidebar && <SidebarSkeleton />}

      <div className="flex flex-col flex-1 min-w-0">
        {/* Header skeleton */}
        <header className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-zinc-200 dark:border-white/10 bg-white/90 dark:bg-[#12151C]/90 backdrop-blur-md sticky top-0 z-10">
          {/* Menu button placeholder (mobile) */}
          <div className="h-8 w-8 rounded-lg bg-zinc-100 dark:bg-white/5 animate-pulse lg:hidden" />
          {/* Logo placeholder */}
          <div className="h-5 w-24 rounded-md bg-zinc-200 dark:bg-white/10 animate-pulse" />
          {/* Spacer */}
          <div className="flex-1" />
          {/* Avatar placeholder */}
          <div className="h-8 w-8 rounded-full bg-zinc-200 dark:bg-white/10 animate-pulse" />
        </header>

        {/* Content skeleton */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-4">
          {/* Page title placeholder */}
          <div className="h-7 w-48 rounded-lg bg-zinc-200 dark:bg-white/10 animate-pulse mb-6" />

          {/* Card placeholders */}
          <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: cards }, (_, i) => (
              <SkeletonCard key={i} lines={lines} />
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
