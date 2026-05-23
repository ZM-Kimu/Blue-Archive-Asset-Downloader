from ba_downloader.infrastructure.schema.common.support import make_valid_identifier


def test_make_valid_identifier_normalizes_python_invalid_names() -> None:
    assert {
        name: make_valid_identifier(name)
        for name in ("class", "9Lives", "", "CharacterExcel")
    } == {
        "class": "class_",
        "9Lives": "_9Lives",
        "": "_",
        "CharacterExcel": "CharacterExcel",
    }
