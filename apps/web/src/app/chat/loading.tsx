import { PageLoadingSkeleton } from '@/components/ui/PageLoadingSkeleton';

export default function ChatLoading() {
  return <PageLoadingSkeleton cards={1} lines={4} showSidebar />;
}
