from civic.districts import DISTRICTS, canonical_district, extract_district, extract_explicit_district


def test_exactly_50_unique_districts():
    assert len(DISTRICTS) == 50
    assert len(set(DISTRICTS)) == 50


def test_canonical_strips_khet_prefix_and_spaces():
    assert canonical_district("เขตคลองเตย") == "คลองเตย"
    assert canonical_district(" จตุจักร ") == "จตุจักร"
    assert canonical_district("สำนักงานเขต พญาไท") == "พญาไท"
    assert canonical_district("ป้อมปราบ") == "ป้อมปราบศัตรูพ่าย"
    assert canonical_district("เชียงใหม่") is None
    assert canonical_district(None) is None


def test_longer_name_wins_over_embedded_name():
    assert extract_district("ที่เขตทวีวัฒนา มีกองขยะ") == "ทวีวัฒนา"
    assert extract_district("ที่เขตวัฒนา มีกองขยะ") == "วัฒนา"


def test_explicit_khet_beats_road_name():
    text = "ถนนลาดพร้าว หน้าห้างแห่งหนึ่ง เขตจตุจักร"
    assert extract_explicit_district(text) == "จตุจักร"
    assert extract_district(text) == "จตุจักร"


def test_first_district_name_without_khet_prefix():
    assert extract_district("ไฟดับแถวบางกะปิ") == "บางกะปิ"


def test_landmark_hint_only_when_no_district_named():
    assert extract_district("ท่อแตกที่ซอยสุขุมวิท 50") == "คลองเตย"
    assert extract_district("ทางเท้าชำรุดปากซอยอารีย์") == "พญาไท"
    assert extract_district("ทางเท้าชำรุดปากซอยอารีย์ เขตดุสิต") == "ดุสิต"
    assert extract_district("ท่อแตกที่ซอยสุขุมวิท 50", use_landmarks=False) is None


def test_no_district():
    assert extract_district("สวัสดีครับ") is None
    assert extract_district("") is None


def test_every_district_is_found_in_a_sentence():
    for name in DISTRICTS:
        assert extract_district(f"ขยะล้นที่เขต{name} ครับ") == name
