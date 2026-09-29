import React, { createContext, useContext } from "react";
import { bm } from "./wt.bm";
import { zh } from "./wt.zh";

/**
 * Walkthrough localisation. The English copy in the scripts is the key; the
 * BM and ZH tables map each English string to its translation (product i18n
 * wording wherever the product already has the string). A missing entry
 * falls back to English, and tools/walkthrough_strings.mjs --check lists any
 * string that has no translation, so a gap never ships silently.
 */
export type WLang = "en" | "bm" | "zh";

const TABLES: Record<WLang, Record<string, string>> = { en: {}, bm, zh };

const WLangContext = createContext<WLang>("en");

export const WLangProvider: React.FC<{ lang: WLang; children: React.ReactNode }> = ({ lang, children }) => (
  <WLangContext.Provider value={lang}>{children}</WLangContext.Provider>
);

export const useWLang = () => useContext(WLangContext);

export const translate = (lang: WLang, s: string) => TABLES[lang][s] ?? s;

/** `t(english)` → the string in the current walkthrough language. */
export const useW = () => {
  const lang = useWLang();
  return (s: string) => translate(lang, s);
};

/** Short language code shown on the app's language pills. */
export const LANG_CODE: Record<WLang, string> = { en: "EN", bm: "BM", zh: "中文" };
/** Language names as the translate menu lists them (each in its own script). */
export const LANG_NAME: Record<WLang, string> = { en: "English", bm: "Bahasa Malaysia", zh: "中文" };

/** Like useW, for JSX children: translates strings, passes numbers and elements through. */
export const useTx = () => {
  const t = useW();
  return (v: React.ReactNode) => (typeof v === "string" ? t(v) : v);
};
