from pathlib import Path

from copilot.classifier import TaskClassifier, load_split
from copilot.evaluation import evaluate_classifier, load_jsonl, run_acceptance_tests
from copilot.rag import BM25Index, chunks_from_catalog
from copilot.store import Store

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "synthetic"
HARD = ROOT / "data" / "eval" / "hard_tasks.jsonl"


def test_hard_set_covers_every_label_and_case_kind():
    rows = load_jsonl(HARD)
    assert len(rows) >= 30, "the brief asks for at least 30 independently checked questions"
    assert {r["label"] for r in rows} == {
        "renewal", "quote-question", "documentation", "complaint", "escalation",
    }
    assert {"paraphrase", "terse", "indirect", "typo", "ambiguous"} <= {r["kind"] for r in rows}


def test_hard_set_shares_no_text_with_training_data():
    train, test = load_split(DATA)
    seen = {r["text"].lower() for r in train + test}
    assert not [r for r in load_jsonl(HARD) if r["text"].lower() in seen]


def test_paraphrases_are_harder_than_templates():
    """The whole point of the hard set: it must expose the gap the template split hides."""
    train, test = load_split(DATA)
    model = TaskClassifier.train(train)
    easy = evaluate_classifier(model, test, "templates")
    hard = evaluate_classifier(model, load_jsonl(HARD), "paraphrases")
    assert hard["macro_f1"] < easy["macro_f1"], (
        "the paraphrase set no longer detects overfitting to template wording"
    )
    assert hard["errors"], "an error list is needed for the written error analysis"


def test_paraphrase_score_does_not_regress():
    """Guards the number quoted in docs/eval/error_analysis.md (0.617 at the time of writing)."""
    train, _ = load_split(DATA)
    hard = evaluate_classifier(TaskClassifier.train(train), load_jsonl(HARD), "paraphrases")
    assert hard["macro_f1"] >= 0.55, hard["macro_f1"]


def test_all_acceptance_cases_pass():
    store = Store.load(DATA)
    index = BM25Index(chunks_from_catalog(store.catalog, store.brochures))
    results = run_acceptance_tests(store, index)
    assert len(results) == 7
    failed = [r.case for r in results if not r.passed]
    assert not failed, f"acceptance failures: {failed}"


def test_every_acceptance_result_records_evidence():
    store = Store.load(DATA)
    index = BM25Index(chunks_from_catalog(store.catalog, store.brochures))
    for result in run_acceptance_tests(store, index):
        assert result.evidence, f"{result.case} has no evidence IDs"
        assert result.expected and result.actual
