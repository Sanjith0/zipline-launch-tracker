import sys, json
import pandas as pd
import numpy as np

SRC = sys.argv[1]
REPORT = pd.Timestamp(sys.argv[2]) if len(sys.argv) > 2 else pd.Timestamp("2027-05-31")

df = pd.read_excel(SRC)
for c in ["closed_won_date", "ready_for_activation_date", "onboarding_start_date", "live_date"]:
    df[c] = pd.to_datetime(df[c])

print("Rows:", len(df), "| date range closed_won:", df.closed_won_date.min().date(), "->", df.closed_won_date.max().date())
print("Max of any date:", max(df[c].max() for c in ["closed_won_date","ready_for_activation_date","onboarding_start_date","live_date"]).date())
print("Reporting date assumed:", REPORT.date())

# ---- sanity checks on ordering
bad = df[(df.ready_for_activation_date < df.closed_won_date) |
         (df.onboarding_start_date < df.ready_for_activation_date) |
         (df.live_date < df.onboarding_start_date)]
print("Rows with out-of-order dates:", len(bad))
skip = df[df.onboarding_start_date.notna() & df.ready_for_activation_date.isna()]
print("Onboarding without ready date:", len(skip))
print("Live without onboarding:", len(df[df.live_date.notna() & df.onboarding_start_date.isna()]))
print("Duplicate merchant ids:", df.merchant_id.duplicated().sum())

# ---- stage as of reporting date
def stage(r):
    if pd.notna(r.live_date) and r.live_date <= REPORT: return "Live"
    if pd.notna(r.onboarding_start_date) and r.onboarding_start_date <= REPORT: return "Onboarding"
    if pd.notna(r.ready_for_activation_date) and r.ready_for_activation_date <= REPORT: return "Ready for activation"
    return "Closed won"
df["stage"] = df.apply(stage, axis=1)

# durations
df["d_cw_ready"] = (df.ready_for_activation_date - df.closed_won_date).dt.days
df["d_ready_onb"] = (df.onboarding_start_date - df.ready_for_activation_date).dt.days
df["d_onb_live"] = (df.live_date - df.onboarding_start_date).dt.days
df["d_cw_live"] = (df.live_date - df.closed_won_date).dt.days
df["age"] = (REPORT - df.closed_won_date).dt.days  # days since closed won

# target status (handles in-flight)
def ready_status(r):
    if pd.notna(r.ready_for_activation_date):
        return "met" if r.d_cw_ready <= 2 else "missed"
    return "missed (still open)" if r.age > 2 else "pending"
def live_status(r):
    if pd.notna(r.live_date):
        return "met" if r.d_cw_live <= 7 else "missed"
    return "missed (still open)" if r.age > 7 else "pending"
df["ready_target"] = df.apply(ready_status, axis=1)
df["live_target"] = df.apply(live_status, axis=1)

print("\n=== Stage counts (as of reporting date)")
print(df.stage.value_counts().to_string())
print("\n=== Stage by market")
print(pd.crosstab(df.market, df.stage, margins=True).to_string())

def rate_block(col, label):
    print(f"\n=== {label}")
    vc = df[col].value_counts()
    print(vc.to_string())
    completed = df[df[col].isin(["met","missed"])]
    print(f"Completed-only hit rate: {(completed[col]=='met').sum()}/{len(completed)} = {(completed[col]=='met').mean():.1%}")
    resolved = df[df[col] != "pending"]
    print(f"Incl. open-and-already-late hit rate: {(resolved[col]=='met').sum()}/{len(resolved)} = {(resolved[col]=='met').mean():.1%}")
    print("By market (completed only):")
    g = completed.groupby("market")[col].apply(lambda s: f"{(s=='met').sum()}/{len(s)} = {(s=='met').mean():.0%}")
    print(g.to_string())
    print("By market (incl. open-and-late):")
    g = resolved.groupby("market")[col].apply(lambda s: f"{(s=='met').sum()}/{len(s)} = {(s=='met').mean():.0%}")
    print(g.to_string())
rate_block("ready_target", "2-day READY target")
rate_block("live_target", "7-day LIVE target")

print("\n=== Stage durations (completed transitions): median / mean / p90 / max / n")
for c, lab in [("d_cw_ready","closed won -> ready"),("d_ready_onb","ready -> onboarding start"),("d_onb_live","onboarding start -> live"),("d_cw_live","closed won -> live")]:
    s = df[c].dropna()
    print(f"{lab:28s} med={s.median():.0f} mean={s.mean():.1f} p90={s.quantile(.9):.0f} max={s.max():.0f} n={len(s)}")
print("\n--- by market")
for m, sub in df.groupby("market"):
    print(m)
    for c, lab in [("d_cw_ready","  cw->ready"),("d_ready_onb","  ready->onb"),("d_onb_live","  onb->live"),("d_cw_live","  cw->live")]:
        s = sub[c].dropna()
        if len(s): print(f"{lab:16s} med={s.median():.0f} mean={s.mean():.1f} p90={s.quantile(.9):.0f} max={s.max():.0f} n={len(s)}")

print("\n=== Where does time go for merchants that went LIVE (mean days per leg)")
live = df[df.live_date.notna()]
print(live[["d_cw_ready","d_ready_onb","d_onb_live"]].mean().round(2).to_string())
print("share of total:", (live[["d_cw_ready","d_ready_onb","d_onb_live"]].mean()/live.d_cw_live.mean()).round(2).to_string())
late_live = live[live.d_cw_live > 7]
print(f"\nLive but >7 days: {len(late_live)} of {len(live)}; mean legs for late ones:")
print(late_live[["d_cw_ready","d_ready_onb","d_onb_live","d_cw_live"]].mean().round(1).to_string())
print("late live merchants:")
print(late_live[["merchant_id","merchant_name","market","d_cw_ready","d_ready_onb","d_onb_live","d_cw_live"]].sort_values("d_cw_live", ascending=False).to_string(index=False))

print("\n=== Attribution: for each live-but-late merchant, which leg exceeded its 'budget' (2 / 4 / 1 days)?")
# budget: ready by 2, onboarding start by ~day 5?, live by 7. Use: cw->ready>2 ; ready->onb >3 ; onb->live > 2
def blame(r):
    legs = []
    if r.d_cw_ready > 2: legs.append("readiness")
    if r.d_ready_onb > 3: legs.append("onboarding-wait")
    if r.d_onb_live > 2: legs.append("onboarding-exec")
    return "+".join(legs) or "none"
late_live = late_live.assign(blame=late_live.apply(blame, axis=1))
print(late_live.blame.value_counts().to_string())

print("\n=== Open (not live) merchants: aging and where stuck")
openm = df[df.live_date.isna()].copy()
openm["days_in_stage"] = openm.apply(lambda r: (REPORT - {"Closed won": r.closed_won_date, "Ready for activation": r.ready_for_activation_date, "Onboarding": r.onboarding_start_date}[r.stage]).days, axis=1)
print(openm.groupby("stage").agg(n=("merchant_id","count"), med_days_in_stage=("days_in_stage","median"), max_days_in_stage=("days_in_stage","max"), already_past_7d=("age", lambda s: (s>7).sum())).to_string())
print("\nOpen by market x stage:")
print(pd.crosstab(openm.market, openm.stage, margins=True).to_string())
print("\nOpen & already past 7 days since closed won, by market x stage:")
print(pd.crosstab(openm[openm.age>7].market, openm[openm.age>7].stage, margins=True).to_string())

print("\n=== Missing IDs")
df["has_menu"] = df.menu_id.notna(); df["has_dload"] = df.drone_loading_id.notna()
print(pd.crosstab([df.has_menu, df.has_dload], df.stage, margins=True).to_string())
print("\nMissing-ID merchants:")
print(df[~df.has_menu | ~df.has_dload][["merchant_id","merchant_name","market","closed_won_date","stage","age","has_menu","has_dload"]].sort_values("age", ascending=False).to_string(index=False))
print("\nStuck in Closed won WITH both IDs:")
print(df[(df.stage=="Closed won") & df.has_menu & df.has_dload][["merchant_id","merchant_name","market","closed_won_date","age"]].to_string(index=False))

print("\n=== Readiness misses (completed cw->ready > 2d)")
print(df[df.d_cw_ready > 2][["merchant_id","merchant_name","market","closed_won_date","d_cw_ready","d_ready_onb","d_cw_live"]].sort_values("d_cw_ready", ascending=False).to_string(index=False))

print("\n=== Weekly cohorts (by closed-won week, Monday start)")
df["cw_week"] = df.closed_won_date.dt.to_period("W-SUN").apply(lambda p: p.start_time.date())
wk = df.groupby("cw_week").agg(
    n=("merchant_id","count"),
    live=("stage", lambda s: (s=="Live").sum()),
    ready_met=("ready_target", lambda s: (s=="met").sum()),
    ready_resolved=("ready_target", lambda s: (s!="pending").sum()),
    live_met=("live_target", lambda s: (s=="met").sum()),
    live_resolved=("live_target", lambda s: (s!="pending").sum()),
    med_ready_onb=("d_ready_onb","median"),
    med_cw_live=("d_cw_live","median"),
)
wk["ready_rate"] = (wk.ready_met/wk.ready_resolved).round(2)
wk["live_rate"] = (wk.live_met/wk.live_resolved).round(2)
print(wk.to_string())
print("\nWeekly closed-won volume by market:")
print(pd.crosstab(df.cw_week, df.market).to_string())

print("\n=== Day-of-week of closed won vs readiness miss")
df["cw_dow"] = df.closed_won_date.dt.day_name()
t = df[df.ready_target!="pending"].groupby("cw_dow").ready_target.apply(lambda s: f"{(s=='met').sum()}/{len(s)}")
print(t.to_string())
df["ready_dow"] = df.ready_for_activation_date.dt.day_name()
print("\nReady day-of-week vs ready->onboarding wait (median):")
print(df.groupby("ready_dow").d_ready_onb.agg(["median","mean","count"]).round(1).to_string())
print("\nOnboarding start day-of-week counts:")
print(df.onboarding_start_date.dt.day_name().value_counts().to_string())
print("Live day-of-week counts:")
print(df.live_date.dt.day_name().value_counts().to_string())

print("\n=== Chain location number vs performance")
df["loc_n"] = df.merchant_name.str.extract(r"Location (\d)").astype(int)
print(df.groupby("loc_n").agg(n=("merchant_id","count"), ready_rate=("ready_target", lambda s: round((s=="met").sum()/max(1,(s!="pending").sum()),2)), live_rate=("live_target", lambda s: round((s=="met").sum()/max(1,(s!="pending").sum()),2)), med_cw_live=("d_cw_live","median")).to_string())

print("\n=== Market monthly: closed-won in April vs May")
df["cw_month"] = df.closed_won_date.dt.month
print(df.groupby(["market","cw_month"]).agg(n=("merchant_id","count"), live=("stage", lambda s:(s=="Live").sum()), live_met=("live_target", lambda s:(s=="met").sum()), live_resolved=("live_target", lambda s:(s!="pending").sum()), med_ready_onb=("d_ready_onb","median")).to_string())

# ---- onboarding throughput: onboarding starts per week per market (capacity signal)
print("\n=== Onboarding sessions started per week, by market")
ob = df[df.onboarding_start_date.notna()].copy()
ob["ob_week"] = ob.onboarding_start_date.dt.to_period("W-SUN").apply(lambda p: p.start_time.date())
print(pd.crosstab(ob.ob_week, ob.market, margins=True).to_string())
print("\nReady-for-activation per week, by market (demand into onboarding queue)")
rd = df[df.ready_for_activation_date.notna()].copy()
rd["rd_week"] = rd.ready_for_activation_date.dt.to_period("W-SUN").apply(lambda p: p.start_time.date())
print(pd.crosstab(rd.rd_week, rd.market, margins=True).to_string())

# save enriched csv
out = df.copy()
for c in ["closed_won_date","ready_for_activation_date","onboarding_start_date","live_date"]:
    out[c] = out[c].dt.strftime("%Y-%m-%d")
out.to_csv(sys.argv[3] if len(sys.argv) > 3 else "/dev/null", index=False)
