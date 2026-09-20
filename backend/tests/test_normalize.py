from verify.text.normalize import fold_party, fold_port, parse_container_count, parse_weight_kg


def test_party_legal_suffix():
    assert fold_party("VITAL SOLUTIONS PTE. LTD.") == fold_party("VITAL SOLUTIONS PTE LTD")


def test_port_strips_unlocode():
    assert fold_port("NANTONG, CHINA (CNNTG)") == fold_port("NANTONG, CHINA")


def test_weight_and_containers():
    assert parse_container_count("6 x 40'HC") == 6
    assert parse_weight_kg("131,058 KG") == 131058
    assert parse_weight_kg("138MT") == 138000


def test_party_name_strips_address():
    from verify.text.normalize import fold_party, party_name_only

    assert fold_party(party_name_only("ROXCEL TRADING GMBH OPERNRING 3-5 1010 VIENNA")) == fold_party(
        "ROXCEL TRADING GMBH"
    )
