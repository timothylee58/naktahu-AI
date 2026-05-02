'use client';

import { motion } from 'framer-motion';

const DOT_COUNT = 3;

export function ThinkingIndicator() {
  return (
    <div
      className="flex items-center gap-1.5 px-4 py-3"
      role="status"
      aria-label="Thinking"
    >
      {Array.from({ length: DOT_COUNT }).map((_, i) => (
        <motion.span
          key={i}
          className="block w-2 h-2 rounded-full bg-zinc-400"
          animate={{ scale: [1, 1.4, 1] }}
          transition={{
            duration: 0.6,
            repeat: Infinity,
            delay: i * 0.15,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
}
