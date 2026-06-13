from screening.engine import ScreeningEngine
from screening.models import ScreeningVerdict, Transaction, WatchlistEntity
from screening.matcher import NameMatcher


def sample_watchlist() -> list[WatchlistEntity]:
    return [
        WatchlistEntity(
            id="test-1",
            full_name="Vladimir Putin",
            country="RU",
            aliases=["Vladimir Poutine"],
        ),
        WatchlistEntity(
            id="test-2",
            full_name="Sergei Shoigu",
            country="RU",
            aliases=["Sergey Shoigu", "Sergey Shoygu"],
        ),
        WatchlistEntity(
            id="test-3",
            full_name="Kim Jong Un",
            country="KP",
            aliases=["Kim Jong-un"],
        ),
    ]


def test_exact_alias_match_is_high_confidence():
    matcher = NameMatcher()
    entity = sample_watchlist()[0]
    score, _ = matcher.compare("Vladimir Poutine", entity, "RU")
    assert score >= 92.0


def test_transliteration_variant_matches():
    matcher = NameMatcher()
    entity = sample_watchlist()[1]
    score, _ = matcher.compare("Sergey Shoygu", entity, "RU")
    assert score >= 92.0


def test_clean_name_is_no_match():
    engine = ScreeningEngine(sample_watchlist())
    result = engine.screen(
        Transaction(
            transaction_id="t1",
            counterparty_name="John Smith",
            counterparty_country="GB",
        )
    )
    assert result.verdict == ScreeningVerdict.NO_MATCH
    assert result.confidence == 0.0


def test_common_name_partial_match_is_not_auto_block():
    engine = ScreeningEngine(sample_watchlist())
    result = engine.screen(
        Transaction(
            transaction_id="t2",
            counterparty_name="Kim Lee",
            counterparty_country="KR",
        )
    )
    assert result.verdict in {ScreeningVerdict.NO_MATCH, ScreeningVerdict.REVIEW}


def test_engine_returns_match_for_pep_hit():
    engine = ScreeningEngine(sample_watchlist())
    result = engine.screen(
        Transaction(
            transaction_id="t3",
            counterparty_name="Vladimir Putin",
            counterparty_country="RU",
        )
    )
    assert result.verdict == ScreeningVerdict.MATCH
    assert result.matched_entities[0].entity.full_name == "Vladimir Putin"


def test_batch_screening():
    engine = ScreeningEngine(sample_watchlist())
    transactions = [
        Transaction(transaction_id="a", counterparty_name="John Smith"),
        Transaction(transaction_id="b", counterparty_name="Sergey Shoigu", counterparty_country="RU"),
    ]
    results = engine.screen_batch(transactions)
    assert len(results) == 2
    assert results[0].verdict == ScreeningVerdict.NO_MATCH
    assert results[1].verdict == ScreeningVerdict.MATCH
