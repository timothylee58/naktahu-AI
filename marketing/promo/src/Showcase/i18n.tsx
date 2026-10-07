import React, { createContext, useContext } from "react";
import { bm, type Copy, type CopyKey } from "./copy.bm";
import { en } from "./copy.en";
import { zh } from "./copy.zh";

export type Lang = "bm" | "en" | "zh";
export const TABLES: Record<Lang, Copy> = { bm, en, zh };

const LangContext = createContext<Lang>("bm");

export const LangProvider: React.FC<{ lang: Lang; children: React.ReactNode }> = ({ lang, children }) => (
  <LangContext.Provider value={lang}>{children}</LangContext.Provider>
);

export const useLang = () => useContext(LangContext);

export const useT = () => {
  const lang = useLang();
  return (k: CopyKey) => TABLES[lang][k];
};

/**
 * Streaming units for type-on text: whole Latin words (with trailing
 * punctuation) and whitespace stay together, every other character — CJK
 * included — is its own unit, so BM/EN reveal word by word and ZH char by char.
 */
export const tokens = (text: string): string[] => text.match(/[A-Za-z0-9$%'’/.\-]+[.,:;!?]*|\s+|[^\s]/g) ?? [];
