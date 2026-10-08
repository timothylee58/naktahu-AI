"""Build data/calibration_synthetic.jsonl: 5 fictional programmes x 8 claims x 3 languages.

Every label is true BY CONSTRUCTION (a supported claim restates a fact in the
context; an unsupported one changes exactly one fact or states the wrong
eligible entity), so no human opinion is involved. That makes the set a reliable
FLOOR (a judge that fails even this is out) and a regression fixture. It is not
evidence a judge is good on real government answers: supported claims here are
short paraphrases of three facts, and the context is a few sentences. Rows are
tagged synthetic=true and metrics.calibration_report never counts them toward
the 30-per-language needed for a "trustworthy" verdict.

    python -m scripts.evals.faithfulness.build_synthetic_set        # rewrites the file
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "data" / "calibration_synthetic.jsonl"

# (acronym, names per language, amount RM, close day, close month, months registered, entity key)
PROGRAMMES = [
    ("SEF", {"en": "Sample Entrepreneur Fund", "bm": "Dana Contoh Usahawan", "zh": "示例创业基金"}, 50_000, 30, 6, 6, "sole"),
    ("DDV", {"en": "Demo Digital Voucher", "bm": "Baucar Digital Demo", "zh": "演示数码券"}, 20_000, 15, 9, 12, "sdn"),
    ("EEB", {"en": "Example Export Boost", "bm": "Pemacu Eksport Contoh", "zh": "示例出口助推"}, 100_000, 31, 12, 24, "sdn"),
    ("PGF", {"en": "Pilot Green Fund", "bm": "Dana Hijau Perintis", "zh": "试点绿色基金"}, 30_000, 28, 2, 6, "sole"),
    ("TSG", {"en": "Test Skills Grant", "bm": "Geran Kemahiran Ujian", "zh": "测试技能补助"}, 80_000, 31, 10, 18, "sdn"),
]
ENTITY = {
    "sole": {"en": "sole proprietorships", "bm": "perniagaan milik tunggal", "zh": "独资企业"},
    "sdn": {"en": "Sdn Bhd companies", "bm": "syarikat Sdn Bhd", "zh": "私人有限公司"},
}
OTHER = {"sole": "sdn", "sdn": "sole"}
MONTH = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "bm": ["Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September", "Oktober", "November", "Disember"],
}


def _amount(lang: str, rm: int) -> str:
    return f"{rm // 10_000} 万令吉" if lang == "zh" else f"RM{rm:,}"


def _month(lang: str, m: int) -> str:
    return f"{m} 月" if lang == "zh" else MONTH[lang][m - 1]


def _rows(lang: str) -> list[dict]:
    rows: list[dict] = []
    for acr, names, rm, day, month, months, ent in PROGRAMMES:
        n, e, e_other = names[lang], ENTITY[ent][lang], ENTITY[OTHER[ent]][lang]
        wrong_month = (month + 2) % 12 + 1
        half = months // 2
        if lang == "en":
            ctx = (f"The {n} ({acr}) gives grants of up to {_amount(lang, rm)} to registered {e}. "
                   f"Applications close on {day} {_month(lang, month)}. "
                   f"Applicants must have been registered for at least {months} months.")
            pos = [f"A registered business of the right kind can receive funding of as much as {_amount(lang, rm)} from {acr}.",
                   f"The last day to apply to {acr} is {day} {_month(lang, month)}.",
                   f"A business registered for under {months} months cannot apply to {acr}.",
                   f"{acr} is open to registered {e}."]
            neg = [f"{acr} gives grants of up to {_amount(lang, rm * 10)}.",
                   f"Applications to {acr} close on {day} {_month(lang, wrong_month)}.",
                   f"Applicants to {acr} need only {half} months of registration.",
                   f"Only {e_other} can apply to {acr}."]
        elif lang == "bm":
            ctx = (f"{n} ({acr}) menawarkan geran sehingga {_amount(lang, rm)} kepada {e} yang berdaftar. "
                   f"Permohonan ditutup pada {day} {_month(lang, month)}. "
                   f"Pemohon mesti telah berdaftar sekurang-kurangnya {months} bulan.")
            pos = [f"Perniagaan berdaftar yang layak boleh menerima pembiayaan setinggi {_amount(lang, rm)} daripada {acr}.",
                   f"Hari terakhir untuk memohon {acr} ialah {day} {_month(lang, month)}.",
                   f"Perniagaan yang berdaftar kurang daripada {months} bulan tidak boleh memohon {acr}.",
                   f"{acr} terbuka kepada {e} yang berdaftar."]
            neg = [f"{acr} menawarkan geran sehingga {_amount(lang, rm * 10)}.",
                   f"Permohonan {acr} ditutup pada {day} {_month(lang, wrong_month)}.",
                   f"Pemohon {acr} hanya perlu berdaftar selama {half} bulan.",
                   f"Hanya {e_other} boleh memohon {acr}."]
        else:
            ctx = (f"{n}（{acr}）向已注册的{e}提供最高 {_amount(lang, rm)}的补助金。"
                   f"申请于 {_month(lang, month)} {day} 日截止。申请人必须已注册至少 {months} 个月。")
            pos = [f"符合条件的已注册企业最多可从 {acr} 获得 {_amount(lang, rm)}的资助。",
                   f"申请 {acr} 的最后一天是 {_month(lang, month)} {day} 日。",
                   f"注册不足 {months} 个月的企业不能申请 {acr}。",
                   f"{acr} 向已注册的{e}开放。"]
            neg = [f"{acr} 提供最高 {_amount(lang, rm * 10)}的补助金。",
                   f"{acr} 的申请于 {_month(lang, wrong_month)} {day} 日截止。",
                   f"{acr} 的申请人只需注册 {half} 个月。",
                   f"只有{e_other}可以申请 {acr}。"]
        for kind, claims, label in (("paraphrase", pos, 1), ("perturbed", neg, 0)):
            for i, claim in enumerate(claims, 1):
                rows.append({
                    "id": f"syn-{lang}-{acr.lower()}-{'p' if label else 'n'}{i}",
                    "language": lang, "context": ctx, "claim": claim, "label": label,
                    "synthetic": True, "kind": kind,
                })
    return rows


def build() -> list[dict]:
    return [r for lang in ("en", "bm", "zh") for r in _rows(lang)]


if __name__ == "__main__":
    data = build()
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in data), encoding="utf-8")
    print(f"wrote {len(data)} rows to {OUT}")
