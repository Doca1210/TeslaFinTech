from __future__ import annotations

import json
from pathlib import Path

from screening.evaluation.models import BenchmarkCase


def default_benchmark_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "benchmark.json"


def load_benchmark(path: Path | str) -> list[BenchmarkCase]:
    data_path = Path(path)
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    return [BenchmarkCase.model_validate(item) for item in payload]
