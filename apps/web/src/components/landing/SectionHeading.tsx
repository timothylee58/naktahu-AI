import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface SectionHeadingProps {
  id?: string;
  title: string;
  description?: ReactNode;
  className?: string;
}

// Left-aligned, large, high-contrast — plain-language government-site
// hierarchy instead of the small centred grey heading every section used to
// repeat, which is what made the page read as one undifferentiated template.
export function SectionHeading({ id, title, description, className }: SectionHeadingProps) {
  return (
    <div className={cn('mb-8 max-w-2xl sm:mb-10', className)}>
      <h2
        id={id}
        className="font-display text-3xl font-extrabold leading-tight tracking-[-0.01em] text-nk-ink sm:text-4xl locale-text-balance"
      >
        {title}
      </h2>
      {description && (
        <p className="mt-3 text-base leading-relaxed text-nk-ink/80 locale-text-balance">{description}</p>
      )}
    </div>
  );
}
