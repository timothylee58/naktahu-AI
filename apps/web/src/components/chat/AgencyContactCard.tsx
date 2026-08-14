'use client';

import { motion } from 'framer-motion';
import type { AgencyContact } from '@/lib/types';
import { useI18n } from '@/lib/i18n';

interface AgencyContactCardProps {
  contact: AgencyContact;
}

/** Shown when the query asked about the user's own case-specific record
 * (e.g. "what's my EPF balance") — NakTahu has no access to any user's
 * records, so this surfaces the real agency contact instead. */
export function AgencyContactCard({ contact }: AgencyContactCardProps) {
  const { t } = useI18n();

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="flex flex-col gap-1.5 rounded-xl border border-nk-official/30 bg-nk-official/10 px-3.5 py-3 text-xs dark:border-nk-official/30 dark:bg-nk-official/10"
    >
      <div className="flex items-center gap-1.5 font-semibold text-nk-official-dim dark:text-nk-official">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5 flex-shrink-0">
          <path fillRule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM9 9a.75.75 0 0 0 0 1.5h.253a.25.25 0 0 1 .244.304l-.459 2.066A1.75 1.75 0 0 0 10.747 15H11a.75.75 0 0 0 0-1.5h-.253a.25.25 0 0 1-.244-.304l.459-2.066A1.75 1.75 0 0 0 9.253 9H9Z" clipRule="evenodd" />
        </svg>
        {t('chat.agency_contact.title')}
      </div>
      <p className="text-nk-official-dim/80 dark:text-nk-official/80">
        {t('chat.agency_contact.desc').replace('{agency}', contact.agency)}
      </p>
      <div className="mt-0.5 flex flex-wrap items-center gap-x-4 gap-y-1">
        <a
          href={contact.portal}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-nk-official-dim underline hover:text-nk-official-dim dark:text-nk-official dark:hover:text-nk-official"
        >
          {contact.agency} ↗
        </a>
        <a
          href={`tel:${contact.hotline.replace(/[^0-9+]/g, '')}`}
          className="font-medium text-nk-official-dim underline hover:text-nk-official-dim dark:text-nk-official dark:hover:text-nk-official"
        >
          {contact.hotline}
        </a>
      </div>
    </motion.div>
  );
}
