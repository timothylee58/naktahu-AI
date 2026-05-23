'use client';

interface SourceCardProps {
  dataset: string;
  year: string | number;
  url?: string;
}

export function SourceCard({ dataset, year, url }: SourceCardProps) {
  const content = (
    <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm flex items-start gap-2">
      <span aria-hidden>🇲🇾</span>
      <div className="flex flex-col gap-0.5">
        <span className="font-medium text-green-900">{dataset}</span>
        {year && <span className="text-green-700 text-xs">{year}</span>}
      </div>
    </div>
  );

  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="no-underline hover:opacity-80 transition-opacity"
      >
        {content}
      </a>
    );
  }

  return content;
}
