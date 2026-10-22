from pathlib import Path

from copilot.classifier import LABELS, TaskClassifier, evaluate, load_split

DATA = Path(__file__).resolve().parent.parent / "data" / "synthetic"


def test_split_is_fixed_and_disjoint():
    train, test = load_split(DATA)
    assert len(train) == 400 and len(test) == 100
    assert not {r["id"] for r in train} & {r["id"] for r in test}


def test_macro_f1_meets_brief_target_on_held_out_split():
    train, test = load_split(DATA)
    report = evaluate(TaskClassifier.train(train), test)
    assert report["macro_f1"] >= 0.75, report


def test_predict_returns_known_label_and_probability():
    train, _ = load_split(DATA)
    label, p = TaskClassifier.train(train).predict("When does C-204 renew?")
    assert label in LABELS and 0.0 <= p <= 1.0


def test_confusion_matrix_shape():
    train, test = load_split(DATA)
    report = evaluate(TaskClassifier.train(train), test)
    assert len(report["confusion_matrix"]) == len(LABELS)
