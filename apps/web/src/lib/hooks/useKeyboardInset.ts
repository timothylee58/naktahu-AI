'use client';

import { useEffect } from 'react';
import { keyboardInset } from '@/lib/prompt/guestChat';

// Publishes the keyboard height as --kb-inset on <html>; the chat dock lifts
// itself by it. A CSS variable keeps this out of React state, so typing never
// re-renders the page on every viewport tick.
export function useKeyboardInset(): void {
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const root = document.documentElement;
    const update = () => {
      root.style.setProperty('--kb-inset', `${keyboardInset(window.innerHeight, vv.height, vv.offsetTop)}px`);
    };
    update();
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
      root.style.removeProperty('--kb-inset');
    };
  }, []);
}
