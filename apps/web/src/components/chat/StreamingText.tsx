'use client';

interface StreamingTextProps {
  tokens: string[];
  isStreaming: boolean;
}

function renderMarkdown(text: string): string {
  return text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[hup])(.+)$/gm, '<p>$1</p>')
    .replace(/<p><\/p>/g, '');
}

export function StreamingText({ tokens, isStreaming }: StreamingTextProps) {
  const text = tokens.join('');
  const html = renderMarkdown(text);

  return (
    <span className="chat-content text-sm leading-relaxed">
      <span dangerouslySetInnerHTML={{ __html: html }} />
      {isStreaming && (
        <span
          aria-hidden
          className="inline-block w-0.5 h-[1em] bg-current align-text-bottom ml-px animate-blink"
        />
      )}
    </span>
  );
}
