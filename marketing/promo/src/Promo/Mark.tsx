import React from "react";
import { interpolate, spring, useVideoConfig } from "remotion";
import { clamp } from "./theme";

function petalPath(L: number, W: number, seed: number): string {
  const cy = -0.6 * L;
  const ry = 0.42 * L;
  const pts: string[] = [];
  const N = 48;
  for (let k = 0; k <= N; k++) {
    const th = Math.PI + (k / N) * Math.PI;
    const ruff = 1 + 0.065 * Math.sin(th * 11 + seed) + 0.035 * Math.sin(th * 23 + seed * 2.3);
    pts.push(`${(W * Math.cos(th) * ruff).toFixed(2)} ${(cy + ry * Math.sin(th) * ruff).toFixed(2)}`);
  }
  const [lx, ly] = pts[0].split(" ");
  return `M 0 0 Q ${-W * 1.05} ${-0.12 * L} ${lx} ${ly} L ${pts.join(" L ")} Q ${W * 1.05} ${-0.12 * L} 0 0 Z`;
}

const ANTHERS = [
  [0.02, -0.02], [-0.05, 0.06], [0.07, 0.09], [-0.03, 0.14], [0.05, 0.19],
  [-0.06, 0.23], [0.03, 0.28], [-0.02, 0.33],
];

/** Bunga raya drawn in vector so each petal can bloom on its own spring. */
export const Hibiscus: React.FC<{ frame: number; start: number; L: number; id: string }> = ({
  frame,
  start,
  L,
  id,
}) => {
  const { fps } = useVideoConfig();
  const W = 0.54 * L;
  const stamen = interpolate(frame, [start + 10, start + 26], [0, 1], clamp);
  const tipX = 0.3 * L;
  const tipY = -1.28 * L;
  const breathe = Math.sin((frame - start) / 18) * 1.6;

  return (
    <g transform={`rotate(${breathe})`}>
      <defs>
        <radialGradient id={`pg-${id}`} cx="0" cy="0" r={L * 1.05} gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#7E0910" />
          <stop offset="0.22" stopColor="#B8131B" />
          <stop offset="0.55" stopColor="#E01F28" />
          <stop offset="1" stopColor="#F43B3F" />
        </radialGradient>
      </defs>
      {[0, 1, 2, 3, 4].map((i) => {
        const s = spring({ frame: frame - start - i * 2.5, fps, config: { damping: 11, mass: 0.7 } });
        const angle = i * 72 - 18 + (1 - s) * -55;
        return (
          <g key={i} transform={`rotate(${angle}) scale(${Math.max(0, s)})`} opacity={Math.min(1, s * 3)}>
            <path d={petalPath(L, W * (1 + (i % 2) * 0.05), i * 1.7)} fill={`url(#pg-${id})`} stroke="#B3141C" strokeWidth={L * 0.012} strokeOpacity={0.45} />
            {[-2, -1, 0, 1, 2].map((j) => (
              <path
                key={j}
                d={`M 0 ${-0.14 * L} Q ${j * W * 0.22} ${-0.5 * L} ${j * W * 0.5} ${-0.92 * L + Math.abs(j) * 0.1 * L}`}
                stroke="#A30E16"
                strokeWidth={L * 0.014}
                strokeOpacity={0.32}
                fill="none"
              />
            ))}
          </g>
        );
      })}
      <circle r={0.17 * L * Math.min(1, Math.max(0, (frame - start) / 8))} fill="#86090F" />
      <path
        d={`M 0 0 Q ${0.04 * L} ${-0.72 * L} ${tipX} ${tipY}`}
        stroke="#EE8A1E"
        strokeWidth={0.055 * L}
        strokeLinecap="round"
        fill="none"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1 - stamen}
      />
      {ANTHERS.map(([dx, dt], k) => {
        const p = spring({ frame: frame - start - 22 - k, fps, config: { damping: 9 } });
        return (
          <circle
            key={k}
            cx={tipX - dt * 0.9 * L * 0.25 + dx * L}
            cy={tipY + dt * L}
            r={0.042 * L * Math.max(0, p)}
            fill="#F7A63C"
          />
        );
      })}
      {[0, 1, 2, 3, 4].map((k) => {
        const p = spring({ frame: frame - start - 28 - k, fps, config: { damping: 9 } });
        const a = (k / 5) * Math.PI * 2;
        return (
          <circle key={k} cx={tipX + Math.cos(a) * 0.06 * L} cy={tipY - 0.05 * L + Math.sin(a) * 0.06 * L} r={0.045 * L * Math.max(0, p)} fill="#E26A12" />
        );
      })}
    </g>
  );
};

/** Hibiscus-Notch mark: speech bubble + bunga raya over its top-right corner. */
export const Mark: React.FC<{
  frame: number;
  size: number;
  bubbleAt: number;
  bloomAt: number;
  dotsFrom?: number;
  id: string;
}> = ({ frame, size, bubbleAt, bloomAt, dotsFrom, id }) => {
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - bubbleAt, fps, config: { damping: 10, mass: 0.8 } });
  const tail = spring({ frame: frame - bubbleAt - 6, fps, config: { damping: 12 } });
  const dotsOut = interpolate(frame, [bloomAt - 4, bloomAt + 6], [1, 0], clamp);

  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      style={{ overflow: "visible", filter: "drop-shadow(0 26px 50px rgba(59,91,255,0.45))" }}
    >
      <defs>
        <linearGradient id={`bg-${id}`} x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0" stopColor="#5872FF" />
          <stop offset="1" stopColor="#2F4CF0" />
        </linearGradient>
        <linearGradient id={`hl-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="white" stopOpacity="0.16" />
          <stop offset="0.45" stopColor="white" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g transform={`translate(60 51) scale(${Math.max(0, s)}) translate(-60 -51)`}>
        <path
          d="M34 84 L32 108 L56 86 Z"
          fill={`url(#bg-${id})`}
          transform={`translate(34 84) scale(${Math.max(0, tail)}) translate(-34 -84)`}
        />
        <rect x="14" y="14" width="92" height="74" rx="30" fill={`url(#bg-${id})`} />
        <rect x="14" y="14" width="92" height="74" rx="30" fill={`url(#hl-${id})`} />
        {dotsFrom !== undefined &&
          [0, 1, 2].map((k) => {
            const local = frame - dotsFrom - k * 4;
            const bounce = Math.max(0, Math.sin((local / 14) * Math.PI * 2)) * -5;
            const on = interpolate(local, [0, 6], [0, 1], clamp);
            return <circle key={k} cx={44 + k * 16} cy={51 + bounce} r={5.2} fill="white" opacity={on * dotsOut * 0.95} />;
          })}
      </g>
      <g transform="translate(97 25)">
        <Hibiscus frame={frame} start={bloomAt} L={21} id={id} />
      </g>
    </svg>
  );
};
