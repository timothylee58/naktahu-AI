export const TOUR_STORAGE_KEY = 'nk_tour_v1_done';

export function hasSeenTour(): boolean {
  try {
    return window.localStorage.getItem(TOUR_STORAGE_KEY) === '1';
  } catch {
    // Storage blocked (private mode): treat as seen so the tour never nags
    // on every page load.
    return true;
  }
}

export function markTourSeen(): void {
  try {
    window.localStorage.setItem(TOUR_STORAGE_KEY, '1');
  } catch {
    /* ignore — see hasSeenTour */
  }
}

export function resetTour(): void {
  try {
    window.localStorage.removeItem(TOUR_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
