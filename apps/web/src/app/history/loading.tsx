import { PageLoadingSkeleton } from '@/components/ui/PageLoadingSkeleton';

export default function HistoryLoading() {
  return <PageLoadingSkeleton cards={4} lines={2} showSidebar />;
}
