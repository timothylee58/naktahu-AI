import { PageLoadingSkeleton } from '@/components/ui/PageLoadingSkeleton';

export default function AgentsLoading() {
  return <PageLoadingSkeleton cards={6} lines={2} showSidebar />;
}
