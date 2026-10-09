# 3-minute demo

| Time | Show | Say |
|---|---|---|
| 0:00 | **Home** (Sample class on) | "A teacher has 40 handwritten answer sheets tonight. Hackedly grades them with Gemma 4, but the teacher stays in charge." |
| 0:20 | **Set up**: rubric + 3 anchors | "She grades 3 answers herself. These anchors teach Gemma 4 *her* strictness." |
| 0:40 | **Grade** → press *Grade 8 sheets now* | "These are 8 PDF answer sheets on the server, not graded yet. Watch: each one is checked, read by Gemma 4, graded twice, and code verifies the evidence and adds up the marks." (about 30–40 s) |
| 1:20 | Board finished | "The smudged sheet was caught as unreadable instead of guessed. Two grading runs agreeing gives us a consistency check." |
| 1:40 | **Review** | "Every mark has a word-for-word quote from the answer; code checked that quote exists. She changes a mark and approves." |
| 2:10 | **Export** popover | "Only approved sheets are released. Every step is in the audit log." |
| 2:25 | **Insights** | "We measured gap to the teacher, consistency and flag quality. Small sample, and we say so." |
| 2:45 | Close | "Open-weight Gemma 4 means a school can run this on its own machine; student data never has to leave." |

**Backup:** record a screen video of one live run beforehand, in case the venue internet or the API is slow. If the API is overloaded, the app backs off and falls back to the second Gemma 4 model automatically.

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
