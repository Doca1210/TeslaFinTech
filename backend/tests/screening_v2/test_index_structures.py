import pytest
from screening_v2.models import IndexEntry, EntityProfile
from app.database import SessionLocal
from screening_v2.db_helpers import load_all_profiles
from screening_v2.normal_search import NormalSearcher


def test_index_entry_fields():
    entry = IndexEntry(
        norm_name="vladimir putin",
        phonetic="FLTMRPTN",
        entity_pk=42,
        list_code="OFAC_SDN",
        source_uid="SDN-12345",
        raw_name="PUTIN, Vladimir",
        entity_type="individual",
    )
    assert entry.norm_name == "vladimir putin"
    assert entry.phonetic == "FLTMRPTN"
    assert entry.entity_pk == 42
    assert entry.list_code == "OFAC_SDN"
    assert entry.source_uid == "SDN-12345"
    assert entry.raw_name == "PUTIN, Vladimir"
    assert entry.entity_type == "individual"


def test_index_entry_phonetic_none_for_entity():
    entry = IndexEntry(
        norm_name="rosneft",
        phonetic=None,
        entity_pk=7,
        list_code="OFAC_SDN",
        source_uid="SDN-99",
        raw_name="Rosneft Oil Company",
        entity_type="entity",
    )
    assert entry.phonetic is None


@pytest.fixture(scope="module")
def all_profiles():
    return load_all_profiles(SessionLocal)


def test_load_all_profiles_returns_dict(all_profiles):
    assert isinstance(all_profiles, dict)
    assert len(all_profiles) > 0


def test_load_all_profiles_keyed_by_int(all_profiles):
    for pk in all_profiles:
        assert isinstance(pk, int)


def test_load_all_profiles_values_are_entity_profiles(all_profiles):
    for profile in all_profiles.values():
        assert isinstance(profile, EntityProfile)
        assert profile.source_uid
        assert profile.primary_name is not None


def test_load_all_profiles_includes_known_entity(all_profiles):
    # At least one profile should reference OFAC_SDN
    list_codes = {p.source_list_code for p in all_profiles.values()}
    assert "OFAC_SDN" in list_codes


# ── Task 3: NormalSearcher index structure tests ──────────────────────────────


@pytest.fixture(scope="module")
def normal_searcher():
    return NormalSearcher(SessionLocal)


def test_token_index_covers_all_entries(normal_searcher):
    reachable = set()
    for positions in normal_searcher._token_index.values():
        reachable.update(positions)
    all_positions = set(range(len(normal_searcher._entries)))
    unreachable = all_positions - reachable
    actually_unreachable = [
        i for i in unreachable if normal_searcher._entries[i].norm_name
    ]
    assert len(actually_unreachable) == 0, (
        f"{len(actually_unreachable)} entries with non-empty norm_name not in token index"
    )


def test_phonetic_index_covers_individual_entries(normal_searcher):
    reachable_via_phonetic = set()
    for positions in normal_searcher._phonetic_index.values():
        reachable_via_phonetic.update(positions)
    individual_with_phonetic = [
        i for i, e in enumerate(normal_searcher._entries)
        if e.entity_type == "individual" and e.phonetic is not None
    ]
    missing = [i for i in individual_with_phonetic if i not in reachable_via_phonetic]
    assert len(missing) == 0, f"{len(missing)} individual entries missing from phonetic index"


def test_profile_cache_covers_all_entity_pks(normal_searcher):
    all_pks = {e.entity_pk for e in normal_searcher._entries}
    cached_pks = set(normal_searcher.profile_cache.keys())
    missing = all_pks - cached_pks
    assert len(missing) == 0, f"{len(missing)} entity_pks missing from profile cache"


def test_entries_are_index_entry_instances(normal_searcher):
    assert len(normal_searcher._entries) > 0
    for entry in normal_searcher._entries[:10]:
        assert isinstance(entry, IndexEntry)
        assert isinstance(entry.entity_pk, int)
