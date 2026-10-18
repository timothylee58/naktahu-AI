'use client';

import Link from 'next/link';
import { Plus } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { NakTahuWordmark } from '@/components/logo/NakTahuWordmark';
import { Button } from '@/components/ui/button';

interface GuestHeaderProps {
  canStartNew: boolean;
  onNewChat: () => void;
  onLogin: () => void;
}

// Slim chrome for signed-out visitors: nothing here needs a sidebar, so they
// get a header only. Signed-in users keep the full sidebar layout.
export function GuestHeader({ canStartNew, onNewChat, onLogin }: GuestHeaderProps) {
  const { t } = useI18n();
  return (
    <header className="sticky top-0 z-10 flex-shrink-0 border-b border-[var(--nk-border)] bg-nk-card/90 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-[1000px] items-center justify-between gap-3 px-4 py-2.5 sm:px-6 sm:py-3.5">
        <Link href="/" className="flex min-h-11 items-center">
          <NakTahuWordmark markSize={24} className="text-lg text-nk-ink" />
        </Link>
        <div className="flex items-center gap-2">
          {canStartNew && (
            <>
              <Button type="button" variant="outline" size="icon" className="h-11 w-11 text-nk-ink sm:hidden" onClick={onNewChat} aria-label={t('chat.new_chat')}>
                <Plus aria-hidden className="h-5 w-5" />
              </Button>
              <Button type="button" variant="outline" className="hidden h-10 rounded-full px-4 text-[13px] text-nk-ink sm:inline-flex" onClick={onNewChat}>
                {t('chat.new_chat')}
              </Button>
            </>
          )}
          <Button type="button" className="h-11 px-4 sm:h-10" onClick={onLogin}>
            {t('header.login')}
          </Button>
        </div>
      </div>
    </header>
  );
}
