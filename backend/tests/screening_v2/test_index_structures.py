from screening_v2.models import IndexEntry


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
