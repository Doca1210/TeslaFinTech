from screening_v2.normalizer import Normalizer


def test_individual_removes_patronym():
    n = Normalizer()
    result = n.normalize("Sergei Kuzhugetovich Shoigu", "individual")
    assert result.cleaned == "sergei shoigu"


def test_individual_removes_feminine_patronym():
    n = Normalizer()
    result = n.normalize("Anna Vladimirovna Shoigu", "individual")
    assert result.cleaned == "anna shoigu"


def test_individual_handles_cyrillic():
    n = Normalizer()
    result = n.normalize("Владимир Путин", "individual")
    assert "vladimir" in result.cleaned
    assert "putin" in result.cleaned


def test_individual_has_phonetic_code():
    n = Normalizer()
    result = n.normalize("Sergei Shoigu", "individual")
    assert result.phonetic is not None
    assert len(result.phonetic) > 0


def test_entity_strips_llc():
    n = Normalizer()
    result = n.normalize("Rosneft Oil Company LLC", "entity")
    assert "rosneft" in result.cleaned
    assert "llc" not in result.cleaned
    assert "company" not in result.cleaned


def test_entity_strips_multiple_suffixes():
    n = Normalizer()
    result = n.normalize("Nord Stream 2 AG", "entity")
    assert "nord" in result.cleaned
    assert "stream" in result.cleaned


def test_entity_no_phonetic():
    n = Normalizer()
    result = n.normalize("Rosneft LLC", "entity")
    assert result.phonetic is None


def test_auto_detects_entity():
    n = Normalizer()
    result = n.normalize("Acme Trading LLC", "auto")
    assert result.entity_type == "entity"


def test_auto_detects_individual():
    n = Normalizer()
    result = n.normalize("John Smith", "auto")
    assert result.entity_type == "individual"


def test_entity_type_stored_in_result():
    n = Normalizer()
    result = n.normalize("Vladimir Putin", "individual")
    assert result.entity_type == "individual"
    assert result.raw == "Vladimir Putin"
