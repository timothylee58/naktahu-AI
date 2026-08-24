import { PageLoadingSkeleton } from '@/components/ui/PageLoadingSkeleton';

export default function DeveloperLoading() {
  return <PageLoadingSkeleton cards={2} lines={3} showSidebar />;
}
