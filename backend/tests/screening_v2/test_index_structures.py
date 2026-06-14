import pytest
from screening_v2.models import IndexEntry, EntityProfile
from app.database import SessionLocal
from screening_v2.db_helpers import load_all_profiles


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
