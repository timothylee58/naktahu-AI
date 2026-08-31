"""Fiuu vs HitPay break-even model for NakTahu credit-pack payments.

Only FPX + DuitNow QR are in scope (cards stay on Stripe). DuitNow QR is 1.2% on
BOTH providers, so it contributes ZERO savings — all savings come from FPX, and
must beat Fiuu's setup + annual fees (which HitPay does not charge).
"""
from __future__ import annotations

from dataclasses import dataclass

SST = 0.08  # Malaysia service tax on gateway service fees

# ---- Provider fee models -------------------------------------------------

def hitpay_fpx(amount: float) -> float:
    return round(amount * 0.018 + 0.40, 4)

def duitnow_qr(amount: float) -> float:  # identical on both providers
    return round(amount * 0.012, 4)

def fiuu_fpx(amount: float, rate: float) -> float:
    # percentage OR RM1 floor, whichever is greater
    return round(max(amount * rate, 1.00), 4)


@dataclass
class FiuuProfile:
    name: str
    fpx_rate: float      # e.g. 0.010 (Premium) or 0.015 (Basic/negotiated)
    setup: float         # one-time RM (pre-SST)
    annual: float        # RM/yr (pre-SST)

    def monthly_fixed(self, setup_amortization_months: int) -> float:
        annual_m = self.annual * (1 + SST) / 12
        setup_m = self.setup * (1 + SST) / setup_amortization_months
        return round(annual_m + setup_m, 2)


FIUU_PREMIUM = FiuuProfile("Fiuu Premium (list rates)", fpx_rate=0.010, setup=400, annual=499)
FIUU_BOOSTER = FiuuProfile("Fiuu Booster (waived setup, RM99/yr)", fpx_rate=0.015, setup=0, annual=99)

TICKETS = [25, 100, 250]  # credit packs: 5 / 20 / 50 credits @ RM5


# ---- Per-transaction FPX comparison -------------------------------------

def per_txn_table() -> str:
    out = ["Per-FPX-transaction fee (RM) and Fiuu saving vs HitPay:",
           f"{'Ticket':>8} | {'HitPay':>7} | {'Fiuu-Prem':>9} | {'save':>6} | {'Fiuu-Boost':>10} | {'save':>6}"]
    for a in TICKETS:
        hp = hitpay_fpx(a)
        fp = fiuu_fpx(a, FIUU_PREMIUM.fpx_rate)
        fb = fiuu_fpx(a, FIUU_BOOSTER.fpx_rate)
        out.append(f"{a:>8} | {hp:>7.2f} | {fp:>9.2f} | {hp-fp:>6.2f} | {fb:>10.2f} | {hp-fb:>6.2f}")
    # crossover ticket where HitPay FPX == Fiuu FPX floor/rate
    out.append("")
    out.append("FPX crossover (below this ticket, Fiuu is NOT cheaper):")
    for prof in (FIUU_PREMIUM, FIUU_BOOSTER):
        # solve 0.018a+0.40 = max(rate*a, 1). Compare against RM1 floor region first.
        # floor region: fiuu=1 -> 0.018a+0.40=1 -> a=33.33
        a_floor = (1.00 - 0.40) / 0.018
        # rate region: 0.018a+0.40 = rate*a -> a=0.40/(0.018-rate)
        a_rate = 0.40 / (0.018 - prof.fpx_rate) if prof.fpx_rate < 0.018 else float("inf")
        cross = a_floor if prof.fpx_rate * a_floor < 1 else a_rate
        out.append(f"  {prof.name:38} ~ RM{cross:6.2f} per FPX ticket")
    return "\n".join(out)


# ---- Break-even monthly FPX volume --------------------------------------

def breakeven_table(setup_amortization_months: int) -> str:
    out = [f"Break-even monthly FPX transactions (setup amortised over {setup_amortization_months} months):",
           f"{'Ticket':>8} | {'Fiuu-Prem save/txn':>18} | {'BE txns/mo':>11} | {'Fiuu-Boost save/txn':>19} | {'BE txns/mo':>11}"]
    for a in TICKETS:
        hp = hitpay_fpx(a)
        for_prem = hp - fiuu_fpx(a, FIUU_PREMIUM.fpx_rate)
        for_boost = hp - fiuu_fpx(a, FIUU_BOOSTER.fpx_rate)
        fx_prem = FIUU_PREMIUM.monthly_fixed(setup_amortization_months)
        fx_boost = FIUU_BOOSTER.monthly_fixed(setup_amortization_months)
        be_prem = fx_prem / for_prem if for_prem > 0 else float("inf")
        be_boost = fx_boost / for_boost if for_boost > 0 else float("inf")
        be_prem_s = f"{be_prem:>11.0f}" if for_prem > 0 else f"{'never':>11}"
        be_boost_s = f"{be_boost:>11.0f}" if for_boost > 0 else f"{'never':>11}"
        out.append(f"{a:>8} | {for_prem:>18.2f} | {be_prem_s} | {for_boost:>19.2f} | {be_boost_s}")
    out.append(f"  (Fiuu monthly fixed: Premium RM{FIUU_PREMIUM.monthly_fixed(setup_amortization_months):.2f}, "
               f"Booster RM{FIUU_BOOSTER.monthly_fixed(setup_amortization_months):.2f})")
    return "\n".join(out)


# ---- Scenario modelling --------------------------------------------------

@dataclass
class Scenario:
    name: str
    packs_per_month: int
    fpx_share: float          # fraction of packs paid via FPX (rest DuitNow QR)
    ticket_mix: dict          # {ticket: share} within FPX

def run_scenario(s: Scenario, prof: FiuuProfile, setup_amortization_months: int) -> dict:
    fpx_count = s.packs_per_month * s.fpx_share
    hp_fpx = fiuu_fpx_cost = 0.0
    for ticket, share in s.ticket_mix.items():
        n = fpx_count * share
        hp_fpx += n * hitpay_fpx(ticket)
        fiuu_fpx_cost += n * fiuu_fpx(ticket, prof.fpx_rate)
    savings = hp_fpx - fiuu_fpx_cost
    fixed = prof.monthly_fixed(setup_amortization_months)
    net = savings - fixed
    return {
        "fpx_count": fpx_count, "hp_fpx": hp_fpx, "fiuu_fpx": fiuu_fpx_cost,
        "savings": savings, "fixed": fixed, "net": net,
    }


SCENARIOS = [
    Scenario("A — Launch", 80, 0.40, {25: 0.70, 100: 0.25, 250: 0.05}),
    Scenario("B — Growth", 400, 0.50, {25: 0.50, 100: 0.35, 250: 0.15}),
    Scenario("C — Scale", 1500, 0.60, {25: 0.40, 100: 0.40, 250: 0.20}),
]


def scenario_report(setup_amortization_months: int) -> str:
    out = [f"Monthly scenarios (setup amortised over {setup_amortization_months} months). "
           "Negative net = Fiuu costs MORE than HitPay:"]
    for s in SCENARIOS:
        out.append(f"\n[{s.name}] {s.packs_per_month} packs/mo, {s.fpx_share:.0%} FPX "
                   f"({s.packs_per_month*s.fpx_share:.0f} FPX txns), ticket mix {s.ticket_mix}")
        for prof in (FIUU_PREMIUM, FIUU_BOOSTER):
            r = run_scenario(s, prof, setup_amortization_months)
            verdict = "Fiuu wins" if r["net"] > 0 else "HitPay wins"
            out.append(f"   {prof.name:38} | HitPay FPX RM{r['hp_fpx']:8.2f} | Fiuu FPX RM{r['fiuu_fpx']:8.2f} "
                       f"| gross save RM{r['savings']:7.2f} | -fixed RM{r['fixed']:6.2f} "
                       f"| NET RM{r['net']:8.2f} -> {verdict}")
    return "\n".join(out)


if __name__ == "__main__":
    print("=" * 100)
    print("FIUU vs HITPAY — NakTahu credit-pack payments (FPX + DuitNow QR only; cards stay on Stripe)")
    print("Assumptions: HitPay FPX 1.8%+RM0.40, DuitNow QR 1.2% (both). Fiuu FPX % or RM1 floor. SST 8% on Fiuu fixed fees.")
    print("=" * 100)
    print()
    print(per_txn_table())
    print()
    print("NOTE: DuitNow QR = 1.2% on BOTH -> zero savings; every QR-paid pack only ADDS Fiuu's fixed-fee burden.")
    print()
    print(breakeven_table(setup_amortization_months=12))
    print()
    print(breakeven_table(setup_amortization_months=36))
    print()
    print(scenario_report(setup_amortization_months=12))
