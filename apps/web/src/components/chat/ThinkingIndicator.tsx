'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

const STAGES_MS = [
  'Mencari dalam pangkalan data…',
  'Menganalisis maklumat…',
  'Menyusun jawapan…',
];

const STAGES_EN = [
  'Searching knowledge base…',
  'Analysing information…',
  'Drafting response…',
];

const STAGES_ZH = [
  '正在搜索数据库…',
  '正在分析信息…',
  '正在撰写回复…',
];

const STAGE_DURATION = 1800; // ms per stage

export function ThinkingIndicator() {
  const { locale } = useI18n();
  const stages = locale === 'ms' ? STAGES_MS : locale === 'zh' ? STAGES_ZH : STAGES_EN;
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setStage((s) => (s + 1) % stages.length);
    }, STAGE_DURATION);
    return () => clearInterval(timer);
  }, [stages.length]);

  return (
    <div className="flex items-center gap-2.5 px-1 py-1" role="status" aria-label={stages[stage]}>
      {/* Animated dots */}
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="block w-1.5 h-1.5 rounded-full bg-blue-400"
            animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2, ease: 'easeInOut' }}
          />
        ))}
      </div>

      {/* Stage label */}
      <AnimatePresence mode="wait">
        <motion.span
          key={stage}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25 }}
          className="text-xs text-zinc-400"
        >
          {stages[stage]}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}
