'use client';

import { useEffect, useState } from 'react';
import { getSeasonalMilestone, inSeasonalWindow, type SeasonalMilestone } from '@/lib/seasonal-window';

/** Shared seasonal/reduced-motion state for the Merdeka hero video —
 * split out of SeasonalHeroVideo so LandingClient can branch its hero
 * LAYOUT (single-column vs. two-panel) on the same `active` flag the
 * video component itself uses to decide what to render, without either
 * duplicating the date/media-query logic or guessing at it from outside. */
export function useSeasonalHeroVideo() {
  const [active, setActive] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [milestone, setMilestone] = useState<SeasonalMilestone>({ kind: 'after' });

  useEffect(() => {
    // Client-only check — avoids an SSR/client hydration mismatch on both
    // the date window and the media query (documented failure mode
    // elsewhere in this codebase for the same pattern).
    const now = new Date();
    setActive(inSeasonalWindow(now));
    setMilestone(getSeasonalMilestone(now));
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  return { active, reducedMotion, milestone };
}
