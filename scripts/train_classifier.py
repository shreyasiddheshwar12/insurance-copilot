"""Train the task classifier on the training split and write an evaluation report.

Usage: python scripts/train_classifier.py
Writes docs/eval/classifier_report.json. Only the train split is used for fitting.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from copilot.classifier import TaskClassifier, evaluate, load_split  # noqa: E402

if __name__ == "__main__":
    train_rows, test_rows = load_split(ROOT / "data" / "synthetic")
    model = TaskClassifier.train(train_rows)
    report = evaluate(model, test_rows)
    out = ROOT / "docs" / "eval" / "classifier_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n_test", "accuracy", "macro_f1")}, indent=2))
