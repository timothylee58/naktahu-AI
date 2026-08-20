'use client';

import { useEffect, useState } from 'react';
import { inSeasonalWindow } from '@/lib/seasonal-window';

// Ambient backdrop for the /chat empty state — three slow-drifting radial
// fields (nk-official blue, nk-heritage gold/terracotta, and a third crimson
// accent unique to this surface) over a faint civic dot-grid, standing in
// for a "measuring instrument" surface rather than decoration: the grid is
// the kind of coordinate mesh a gazette map or survey plan would carry, not
// a generic tech texture.
//
// CSS-only (radial-gradient + keyframe transform), not WebGL/canvas — scoped
// behind the empty-state column only (absolute inset-0 on its own relative
// parent), never full-viewport, and frozen to a static frame under
// prefers-reduced-motion via the .chat-ambient-mesh media query in
// globals.css (large slow-drifting fields are exactly what that guidance
// singles out).
//
// Aug25-Sep20 (Merdeka/Hari Malaysia window) adds a 14-point starburst
// layer (Bintang 14 Bucu — echoing the Jalur Gemilang's star) on top of the
// permanent fields, rather than a second competing ambient component
// stacked over this one — see the seasonal roadmap discussion for why that
// dedup mattered.
export function ChatAmbientMesh() {
  const [seasonal, setSeasonal] = useState(false);
  useEffect(() => {
    setSeasonal(inSeasonalWindow(new Date()));
  }, []);

  return (
    <div aria-hidden className="chat-ambient-mesh pointer-events-none absolute inset-0 overflow-hidden -z-10">
      <div className="chat-ambient-mesh__grid absolute inset-0" />
      <div className="chat-ambient-mesh__field chat-ambient-mesh__field--official absolute" />
      <div className="chat-ambient-mesh__field chat-ambient-mesh__field--heritage absolute" />
      <div className="chat-ambient-mesh__field chat-ambient-mesh__field--crimson absolute" />
      {seasonal && (
        <svg
          className="chat-ambient-mesh__starburst absolute left-1/2 top-1/2"
          viewBox="0 0 200 200"
        >
          {Array.from({ length: 14 }).map((_, i) => {
            const angle = (i / 14) * Math.PI * 2;
            const x1 = (100 + Math.cos(angle) * 34).toFixed(3);
            const y1 = (100 + Math.sin(angle) * 34).toFixed(3);
            const x2 = (100 + Math.cos(angle) * 96).toFixed(3);
            const y2 = (100 + Math.sin(angle) * 96).toFixed(3);
            return (
              <line
                key={i}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={i % 2 === 0 ? 'var(--nk-heritage)' : 'var(--nk-official)'}
                strokeWidth={2.5}
                strokeLinecap="round"
              />
            );
          })}
        </svg>
      )}
    </div>
  );
}
