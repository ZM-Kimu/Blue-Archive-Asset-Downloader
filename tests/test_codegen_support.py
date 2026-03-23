from ba_downloader.infrastructure.tools.codegen_support import (
    TemplateString,
    make_valid_identifier,
)


def test_codegen_support_exports_expected_helpers() -> None:
    assert TemplateString("class %s:")("Example") == "class Example:"
    assert make_valid_identifier("class") == "class_"
    assert make_valid_identifier("9Lives") == "_9Lives"
