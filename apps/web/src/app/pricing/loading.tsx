import { PageLoadingSkeleton } from '@/components/ui/PageLoadingSkeleton';

export default function PricingLoading() {
  return <PageLoadingSkeleton cards={3} lines={4} showSidebar />;
}
