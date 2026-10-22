"""Task classifier: tags an incoming agent task as renewal, quote-question, documentation,
complaint or escalation.

Baseline: TF-IDF (word + character n-grams) with logistic regression. It runs on CPU with no
model download. The Hugging Face path (optional, Day 35) is wired in `HFZeroShotClassifier`
and is only used when the `transformers` package and COPILOT_HF_MODEL are set.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

LABELS = ["renewal", "quote-question", "documentation", "complaint", "escalation"]

#: Returned instead of a guess when no label clears the confidence bar.
UNCLEAR = "unclear"

#: Chosen from the paraphrase-set confidence distribution; see docs/eval/error_analysis.md.
DEFAULT_THRESHOLD = 0.40


def load_split(data_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [json.loads(line) for line in (data_dir / "labelled_tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["split"] == "train"], [r for r in rows if r["split"] == "test"]


def build_pipeline() -> Pipeline:
    features = FeatureUnion([
        ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
    ])
    return Pipeline([
        ("features", features),
        ("clf", LogisticRegression(max_iter=2000, C=5.0, class_weight="balanced")),
    ])


@dataclass
class TaskClassifier:
    pipeline: Pipeline

    @classmethod
    def train(cls, train_rows: list[dict[str, Any]]) -> "TaskClassifier":
        pipe = build_pipeline()
        pipe.fit([r["text"] for r in train_rows], [r["label"] for r in train_rows])
        return cls(pipe)

    def predict(self, text: str) -> tuple[str, float]:
        probs = self.pipeline.predict_proba([text])[0]
        idx = int(probs.argmax())
        return str(self.pipeline.classes_[idx]), round(float(probs[idx]), 4)

    def predict_with_threshold(self, text: str, threshold: float = DEFAULT_THRESHOLD) -> tuple[str, float]:
        """Return UNCLEAR instead of a low-confidence guess.

        The error analysis showed unfamiliar wording defaulting to `escalation`, which sends
        routine work to a supervisor. Naming the uncertainty is what the brief asks for:
        request the missing input rather than assert something unsupported.
        """
        label, confidence = self.predict(text)
        return (label, confidence) if confidence >= threshold else (UNCLEAR, confidence)


def evaluate(model: TaskClassifier, test_rows: list[dict[str, Any]]) -> dict[str, Any]:
    y_true = [r["label"] for r in test_rows]
    y_pred = model.pipeline.predict([r["text"] for r in test_rows])
    matrix = confusion_matrix(y_true, y_pred, labels=LABELS)
    return {
        "n_test": len(test_rows),
        "accuracy": round(sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=LABELS, average="macro")), 4),
        "labels": LABELS,
        "confusion_matrix": matrix.tolist(),
    }


class HFZeroShotClassifier:
    """Optional pretrained path. Loads only when explicitly configured (needs `transformers`)."""

    def __init__(self, model_name: str) -> None:
        from transformers import pipeline  # imported lazily: heavy dependency

        self._pipe = pipeline("zero-shot-classification", model=model_name)

    def predict(self, text: str) -> tuple[str, float]:
        out = self._pipe(text, candidate_labels=LABELS)
        return out["labels"][0], round(float(out["scores"][0]), 4)
