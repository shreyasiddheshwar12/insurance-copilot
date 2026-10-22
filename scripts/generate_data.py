"""Regenerate the synthetic fixtures in data/synthetic (seed 42, reproducible)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from copilot.data_gen import generate  # noqa: E402

if __name__ == "__main__":
    generate(ROOT / "data" / "synthetic")
    print("Synthetic data written to data/synthetic")
