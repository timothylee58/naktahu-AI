'use client';

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
export function ChatAmbientMesh() {
  return (
    <div aria-hidden className="chat-ambient-mesh pointer-events-none absolute inset-0 overflow-hidden -z-10">
      <div className="chat-ambient-mesh__grid absolute inset-0" />
      <div className="chat-ambient-mesh__field chat-ambient-mesh__field--official absolute" />
      <div className="chat-ambient-mesh__field chat-ambient-mesh__field--heritage absolute" />
      <div className="chat-ambient-mesh__field chat-ambient-mesh__field--crimson absolute" />
    </div>
  );
}
