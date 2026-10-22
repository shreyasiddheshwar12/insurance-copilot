# Classifier error analysis

Run `python scripts/run_eval.py` to reproduce. Numbers below are from the run on 2026-10-22.

## Headline: the template score is not a real score

| Evaluation set | n | Macro-F1 |
| --- | --- | --- |
| Held-out template split | 100 | **1.000** |
| Independently written paraphrases | 50 | **0.617** |

The held-out split is drawn from the same five phrasing templates as the training data, so it
shares vocabulary with what the model was fit on. A perfect score there says the pipeline runs.
It does not say the model generalises.

The paraphrase set (`data/eval/hard_tasks.jsonl`) was written by hand without reusing any
training sentence, and includes terse notes, indirect phrasing, typos and genuinely ambiguous
cases. On that set the model scores **0.617, below the brief's 0.75 target**.

This gap is the finding we report, not a number to hide.

## Per-label F1 on the paraphrase set

| Label | F1 | Reading |
| --- | --- | --- |
| complaint | 0.70 | Best. Emotion words ("upset", "annoyed", "fed up") carry across phrasings. |
| quote-question | 0.64 | Survives when a plan name appears; fails on "the mid tier", "the two options". |
| documentation | 0.63 | Fails on terse filing notes with no documentation verb. |
| escalation | 0.58 | Acts as a catch-all for unfamiliar text (see below). |
| renewal | 0.53 | Worst. Collapses when the words "renew" or "reminder" are absent. |

## Three failure patterns

**1. Keyword dependence (9 of 19 errors).** The model learned the template keywords, not the
intent. Remove them and it guesses:

| Input | Expected | Predicted |
| --- | --- | --- |
| "anniversary date for the policy of C-255?" | renewal | documentation |
| "his cover ends in November, set up the message" | renewal | documentation |
| "C-401 expires shortly, what do we send" | renewal | quote-question |

"Expires", "lapses", "cover ends" and "anniversary date" never appear in training. A real agent
uses them constantly.

**2. Escalation is a sink (6 errors).** Unfamiliar wording defaults to escalation, including
four plain documentation tasks:

| Input | Expected | Predicted |
| --- | --- | --- |
| "upload id proof against C-288" | documentation | escalation |
| "paperwork for C-019 needs filing" | documentation | escalation |
| "make an entry for todays conversation" | documentation | escalation |

This is the costliest error in practice: routine filing gets queued for a supervisor. With
`class_weight="balanced"` on small, regular classes, escalation absorbs low-confidence inputs.

**3. Genuinely ambiguous cases (2 errors).** Both are arguably defensible:

- "customer feels cheated by the exclusions" — labelled complaint, predicted quote-question.
  It is both: an unhappy customer *and* a product question.
- "C-088 is demanding to speak to someone higher" — labelled escalation, predicted
  quote-question. Clearly escalation to a human; the model has no signal for it.

These two should be adjudicated by a second labeller, not counted as plain model failures.

## What we would do next

1. **Widen the training vocabulary.** Add "expires", "lapses", "cover ends", "anniversary",
   "continuation" to the renewal templates, and filing verbs to documentation. Expected to fix
   most of pattern 1.
2. **Calibrate instead of guessing.** Return "unclear" below a confidence threshold and ask the
   agent, rather than routing to escalation. This matches the brief's rule to name missing inputs.
3. **Try the pretrained path.** `HFZeroShotClassifier` is wired but unused. A sentence-embedding
   model should handle paraphrases far better than TF-IDF, which only matches surface tokens.
4. **Second-labeller pass.** The two ambiguous items need an adjudicated gold label.

## Honest limitations

- All data is synthetic and written by the project team. It is not a sample of real agent traffic,
  so even the paraphrase score is optimistic about real-world performance.
- 50 paraphrase items is small. Per-label F1 on 10 items each moves a lot with one error.
- The classifier is not yet wired into the router, which still uses regular expressions. These
  numbers describe the model in isolation.
