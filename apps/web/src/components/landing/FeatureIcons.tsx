'use client';

import type { ReactNode } from 'react';
import { motion } from 'framer-motion';

const loopEase = { repeat: Infinity, ease: 'easeInOut' as const };

const iconShell =
  'w-10 h-10 rounded-xl bg-[#2563EB]/15 flex items-center justify-center text-[#2563EB] flex-shrink-0';

function IconShell({ children }: { children: ReactNode }) {
  return (
    <motion.div
      className={iconShell}
      initial={{ opacity: 0, scale: 0.85 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ type: 'spring', stiffness: 320, damping: 22 }}
      whileHover={{ scale: 1.06, rotate: 2 }}
    >
      {children}
    </motion.div>
  );
}

export function BilingualFeatureIcon() {
  return (
    <IconShell>
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 overflow-visible">
        <motion.g
          animate={{ y: [0, -1.5, 0], opacity: [0.75, 1, 0.75] }}
          transition={{ ...loopEase, duration: 2.4 }}
        >
          <path d="M4.913 2.658c2.075-.27 4.19-.408 6.337-.408 2.147 0 4.262.139 6.337.408 1.922.25 3.291 1.861 3.405 3.727a4.403 4.403 0 0 0-1.032-.211 50.89 50.89 0 0 0-8.42 0c-2.358.196-4.04 2.19-4.04 4.434v4.286a4.47 4.47 0 0 0 2.433 3.984L7.28 21.53A.75.75 0 0 1 6 21v-4.03a48.527 48.527 0 0 1-1.087-.128C2.905 16.58 1.5 14.833 1.5 12.862V6.638c0-1.97 1.405-3.718 3.413-3.979Z" />
        </motion.g>
        <motion.g
          animate={{ y: [0, 1.5, 0], opacity: [1, 0.75, 1] }}
          transition={{ ...loopEase, duration: 2.4, delay: 0.3 }}
        >
          <path d="M15.75 7.5c-1.376 0-2.739.057-4.086.169C10.124 7.797 9 9.103 9 10.609v4.285c0 1.507 1.128 2.814 2.67 2.94 1.243.102 2.5.157 3.768.165l2.782 2.781a.75.75 0 0 0 1.28-.53v-2.39l.33-.026c1.542-.125 2.67-1.433 2.67-2.94v-4.286c0-1.505-1.125-2.811-2.664-2.94A49.392 49.392 0 0 0 15.75 7.5Z" />
        </motion.g>
      </svg>
    </IconShell>
  );
}

export function CitedFeatureIcon() {
  return (
    <IconShell>
      <motion.svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="w-6 h-6"
        animate={{ y: [0, -1, 0] }}
        transition={{ ...loopEase, duration: 2.6 }}
      >
        <path
          fillRule="evenodd"
          d="M15.75 2.25H21a.75.75 0 0 1 .75.75v5.25a.75.75 0 0 1-1.5 0V4.81L8.03 17.03a.75.75 0 0 1-1.06-1.06L19.19 3.75h-3.44a.75.75 0 0 1 0-1.5Zm-10.5 4.5a1.5 1.5 0 0 0-1.5 1.5v10.5a1.5 1.5 0 0 0 1.5 1.5h10.5a1.5 1.5 0 0 0 1.5-1.5V10.5a.75.75 0 0 1 1.5 0v8.25a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3V8.25a3 3 0 0 1 3-3h8.25a.75.75 0 0 1 0 1.5H5.25Z"
          clipRule="evenodd"
        />
        <motion.path
          d="M17.5 4.5h3v3"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          animate={{ pathLength: [0.4, 1, 0.4], opacity: [0.5, 1, 0.5] }}
          transition={{ ...loopEase, duration: 2.2 }}
        />
      </motion.svg>
    </IconShell>
  );
}

export function VoiceFeatureIcon() {
  const barHeights = [4, 7, 5];
  return (
    <IconShell>
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
        <motion.path
          d="M8.25 4.5a3.75 3.75 0 1 1 7.5 0v8.25a3.75 3.75 0 1 1-7.5 0V4.5Z"
          animate={{ scaleY: [1, 1.05, 1] }}
          transition={{ ...loopEase, duration: 1.6 }}
          style={{ transformOrigin: '12px 16px' }}
        />
        <path d="M6 10.5a.75.75 0 0 1 .75.75v1.5a5.25 5.25 0 1 0 10.5 0v-1.5a.75.75 0 0 1 1.5 0v1.5a6.751 6.751 0 0 1-6 6.709v2.291h3a.75.75 0 0 1 0 1.5h-7.5a.75.75 0 0 1 0-1.5h3v-2.291a6.751 6.751 0 0 1-6-6.709v-1.5A.75.75 0 0 1 6 10.5Z" />
        {barHeights.map((h, i) => (
          <motion.rect
            key={i}
            x={18 + i * 2.2}
            y={12 - h / 2}
            width={1.4}
            height={h}
            rx={0.7}
            fill="currentColor"
            animate={{ scaleY: [0.45, 1, 0.55] }}
            transition={{ ...loopEase, duration: 1.1, delay: i * 0.15 }}
            style={{ transformOrigin: `${18.7 + i * 2.2}px 12px` }}
          />
        ))}
      </svg>
    </IconShell>
  );
}

export const FEATURE_ICONS = [
  BilingualFeatureIcon,
  CitedFeatureIcon,
  VoiceFeatureIcon,
] as const;
