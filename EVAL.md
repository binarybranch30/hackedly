# Evaluation

> **Disclosure:** this is a very small test set (≈10 scripts, 7 held out), graded by one teacher, with answers written by our team and friends. The numbers below are **indicative only, not statistically significant.** Every cell is filled from a file in `eval/results/`. Empty cells mean "not run". Nothing here is estimated or assumed.

## Test set
- **Question:** 1 short-answer question, 3 rubric items, 5 marks (`data/rubric.json`).
- **10 handwritten answers**, written on purpose to cover a range: 2 strong · 3 medium · 2 weak · 1 messy handwriting · 1 off-topic/ambiguous · 1 partial. One answer per phone photo: `data/scripts/S01.jpg` … `S10.jpg`.
- **Teacher marks first:** before any model run, the "teacher" grades all 10 per item in `data/teacher_marks.csv`, and tags each one `teacher_says_hard` yes/no.
- **Split:** S01–S03 = anchors (used for calibration). S04–S10 = held-out (used for metrics). Anchors are never scored in metrics 1–3.

## Metric 1 — Gap to teacher (MAE)
MAE = mean absolute error = the average size of the difference, ignoring sign.
`MAE = mean over held-out scripts of |system total − teacher total|`. Also computed per rubric item.
- **Uncalibrated:** rubric only (`calibrated=False`, no anchors).
- **Calibrated:** rubric + the 3 anchors in the prompt.

## Metric 2 — Consistency
Grade each held-out script **5 times** with the same settings (temperature 0). For each script, record the **range** (max − min) and the **standard deviation** of the 5 totals. Report the mean range, the mean stdev, and the % of scripts whose 5 totals were identical.

## Metric 3 — Flagging quality
Rule fixed **before** running: a script is "hard" if the calibrated system total is ≥1 mark off the teacher's total. Build the 2×2 table below and compare the average error of flagged vs unflagged scripts. As a second check, compare the flags with the teacher's own `teacher_says_hard` tags.

## Call budget
Each grade call is transcribe + grade×2 = 3 calls. With 7 held-out scripts: uncalibrated ×1 plus calibrated ×5 ≈ 126 calls. Start at 13:30, and save raw outputs to `eval/results/raw/`.

## Results (fill from files only)
| Setting | Model | n | MAE total (marks) | MAE per item | Mean range over 5 runs | % identical |
|---|---|---|---|---|---|---|
| Uncalibrated | gemma-4-31b-it | 7 | — | — | n/a | n/a |
| Calibrated | gemma-4-31b-it | 7 | — | — | — | — |
| Calibrated *(stretch)* | gemma4:e2b | 7 | — | — | n/a | n/a |
| Human vs human *(stretch)* | — | 7 | — | — | n/a | n/a |

**Flagging (calibrated, gemma-4-31b-it)**
| | Hard (error ≥1) | Not hard |
|---|---|---|
| Flagged | — | — |
| Not flagged | — | — |

Mean error of flagged scripts: — · unflagged scripts: — · Flags vs teacher's hard tags agree on —/7.

Settings used: temperature —, thinking —, date/time of run —.
