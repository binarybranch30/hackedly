# 3-minute demo

| Time | Show | Say |
|---|---|---|
| 0:00 | Title | "A teacher has 40 handwritten scripts tonight. AI can help, but only if she can trust it and stays in control." |
| 0:20 | Rubric + Anchors tabs | "She grades 3 scripts herself. Those anchors teach Gemma 4 *her* marking style." |
| 0:45 | Grade tab: run 2 scripts live | "Gemma 4 reads the handwriting, then scores each item and must quote the exact words that earned each mark." |
| 1:10 | Review tab: evidence highlighted | "Code checks that each quote really exists, and code adds up the total. The model never does the arithmetic." |
| 1:30 | Flagged scripts: messy + ambiguous | "When it's unsure, it flags the script instead of guessing. Here the two grading runs disagreed." |
| 1:50 | Teacher edits a mark, approves | "Nothing is released without approval." |
| 2:05 | Audit tab, then CSV export | "Every change is logged: who, what, before/after." |
| 2:20 | EVAL.md table | "We measured it: gap to the teacher with and without anchors, consistency over 5 runs, and whether flags catch the hard scripts. Small sample, 7 scripts, and we say so." |
| 2:45 | Backend switch | "Gemma 4 is open-weight, so the same pipeline runs locally on a laptop with E2B and student data never leaves the school. We measured the quality cost." |
| 3:00 | End | |

**Backup:** a pre-recorded video plus real results saved in `data/grades/` in case the wifi dies.

## Likely judge questions (honest answers)
**"Can't ChatGPT do this?"**
ChatGPT can grade a single answer in one chat. What we built is the *process* around the model: forced evidence quotes that code verifies, arithmetic done in code, routing to review when unsure, teacher approval, an audit trail, and **measured** error and consistency against a teacher. We have not benchmarked ChatGPT, so we don't claim to beat it. Our claim is that this workflow is measurable and controllable.

**"Your sample is tiny."**
Yes: 7 held-out scripts, one teacher, answers written by our team. The numbers show the harness works and give early signals; they don't prove accuracy. The harness itself is the reusable part.

**"Why Gemma / open weights?"**
Student answer sheets are sensitive. With open weights, a school can run the whole pipeline on its own machine. The E2B row shows the accuracy trade-off for doing that. *(Only say this if the E2B row was actually run.)*

**"What if the model makes up evidence?"**
Code checks every quote against the transcription. If it isn't there, the script is flagged.

**"What if the transcription itself is wrong?"**
Then the evidence check can pass on wrong text. That is why the teacher sees the original image next to the transcription in review. This is a real limitation.

**"What if the anchors are bad or biased?"**
The system copies the teacher's style, including that teacher's biases. It measures consistency *with the teacher*, not objective correctness.

**"How fast / how much does it cost?"**
Quote the measured seconds per script from the eval run. Don't estimate.
