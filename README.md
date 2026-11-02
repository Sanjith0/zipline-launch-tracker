# Merchant Launch Tracker

Take-home case study for the Zipline Launch & Scale Intern role. The tool shows where every merchant sits in the launch process, how often the team is meeting its targets, and where the bottlenecks are by market over time.

**Live tool:** https://sanjith0.github.io/zipline-launch-tracker/

## What the data says (reporting date May 31, 2027)

- **40% of merchants with a known outcome went live within 7 days** of closed won, and **70% were ready for activation within 2 days**. Counting only merchants that completed each step gives 80% and 85%, but that ignores the 50 open merchants already past the 7-day mark.
- **Main bottleneck: the wait for an in-person onboarding session.** It is half of total time to live, with a median of 3 days but a 90th percentile of 8 and a max of 27. 40 merchants are waiting in Ready for activation, median 11 days in stage. Northfield is worst: 16 of its 30 merchants are in that queue.
- **Second bottleneck: setup data.** All 25 merchants still in Closed won are missing a menu ID, a drone loading ID, or both. Every merchant with both IDs has progressed.
- **It is getting worse with volume.** Weekly closed-won handovers grew from 7 to 28 across April and May while onboarding sessions stayed flat at 4 to 10 a week. April cohorts hit the 7-day target 82 to 100% of the time; fully resolved May cohorts hit 20% and 0%.

## The tool

`index.html` is a single self-contained page with the dataset embedded. Open it in any browser; no build step or server needed.

- **Reporting date** control: every stage and metric is evaluated as of that date, so moving it back replays the pipeline as it looked then.
- **Summary tiles**: live count, both target hit rates (inclusive figure first, completed-only as a note), overdue merchants, onboarding queue, and merchants blocked on setup data.
- **Where merchants are right now**: stage counts per market with overdue and blocked counts.
- **Where the time goes**: median and 90th percentile days per stage, per market.
- **Bottlenecks by market over time**: a closed-won-week by market heatmap, switchable between 7-day live rate, 2-day ready rate, median onboarding wait, overdue count, and volume.
- **Onboarding capacity**: weekly closed won vs became ready vs sessions started, per market.
- **Work queue**: open merchants sorted overdue-first with days in stage, target status, missing setup data, and a suggested next action. Filter chips match the bottlenecks above.

## Reproducing the numbers

```bash
pip install -r requirements.txt
python launch_analysis.py data/merchant_launch_dataset.xlsx 2027-05-31
```

The script prints stage counts, hit rates (both definitions), stage durations, market breakdowns, weekly cohorts, onboarding throughput, and the lists of late and blocked merchants. The page's JavaScript recomputes the same metrics independently from the raw dates; the two agree on every figure above.

## Definitions and assumptions

- **Reporting date**: the dataset carries no reporting date, so the default is May 31, 2027, the day after the last recorded event. It is adjustable in the tool and on the script's command line.
- **Days** are calendar days, as the targets are stated.
- **Stage** is the latest milestone dated on or before the reporting date.
- **Target hit rate** = merchants that met the target divided by merchants whose outcome is known. A merchant still open and already past the deadline counts as a miss; one still inside the window is excluded as pending.
- **Setup data**: readiness requires menu setup and a drone loading location, so a missing menu ID or drone loading ID is flagged as a blocker.
- **Weeks** start on Monday and are labelled by their first day. Cohorts are grouped by closed-won week.
