import { PageLoadingSkeleton } from '@/components/ui/PageLoadingSkeleton';

export default function ProfileLoading() {
  return <PageLoadingSkeleton cards={2} lines={3} showSidebar />;
}
