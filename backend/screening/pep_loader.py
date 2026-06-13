from __future__ import annotations

import json
from pathlib import Path

from screening.models import WatchlistEntity


def load_watchlist(path: Path | str) -> list[WatchlistEntity]:
    data_path = Path(path)
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    return [WatchlistEntity.model_validate(item) for item in payload]


def default_watchlist_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "pep_list.json"
