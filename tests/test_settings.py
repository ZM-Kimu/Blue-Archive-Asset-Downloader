import re
from pathlib import Path

from ba_downloader.application.config import AppSettings
from ba_downloader.cli.main import build_parser, runtime_context_from_namespace
from ba_downloader.domain.models.asset import AssetType
from support import build_asset_collection, build_runtime_context


def test_settings_normalization_defaults() -> None:
    settings = AppSettings(region="jp").normalized()

    assert settings.temp_dir == "JP_Android_Temp"
    assert settings.raw_dir == "JP_Android_RawData"
    assert settings.extract_dir == "JP_Android_Extracted"
    assert settings.platform == "android"
    assert settings.platform_explicit is False
    assert settings.resource_type == ("table", "media", "bundle")


def test_settings_normalization_uses_platform_specific_jp_directories() -> None:
    settings = AppSettings(
        region="jp", platform="windows", platform_explicit=True
    ).normalized()

    assert settings.temp_dir == "JP_Windows_Temp"
    assert settings.raw_dir == "JP_Windows_RawData"
    assert settings.extract_dir == "JP_Windows_Extracted"
    assert settings.platform == "windows"
    assert settings.platform_explicit is True


def test_settings_normalization_keeps_non_jp_default_directories() -> None:
    settings = AppSettings(
        region="gl", platform="ios", platform_explicit=True
    ).normalized()

    assert settings.temp_dir == "GL_Temp"
    assert settings.raw_dir == "GL_RawData"
    assert settings.extract_dir == "GL_Extracted"


def test_settings_normalization_uses_underscored_cn_directories() -> None:
    settings = AppSettings(region="cn").normalized()

    assert settings.temp_dir == "CN_Temp"
    assert settings.raw_dir == "CN_RawData"
    assert settings.extract_dir == "CN_Extracted"


def test_settings_normalization_preserves_custom_directories() -> None:
    settings = AppSettings(
        region="gl",
        raw_dir="custom_raw",
        extract_dir="custom_extract",
        temp_dir="custom_temp",
    ).normalized()

    assert settings.raw_dir == "custom_raw"
    assert settings.extract_dir == "custom_extract"
    assert settings.temp_dir == "custom_temp"


def test_runtime_context_copies_normalized_settings() -> None:
    runtime_context = AppSettings(
        region="gl",
        threads=8,
        raw_dir="RawData",
        extract_dir="Extracted",
        temp_dir="Temp",
        resource_type=("media",),
        max_retries=2,
    ).to_runtime_context()

    assert runtime_context.region == "gl"
    assert runtime_context.threads == 8
    assert runtime_context.resource_type == ("media",)
    assert runtime_context.platform == "android"
    assert runtime_context.platform_explicit is False


def test_runtime_context_copies_jp_sqlcipher_key_from_cli() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "extract",
            "--region",
            "jp",
            "--jp-sqlcipher-key-hex",
            "a" * 64,
        ]
    )

    runtime_context = runtime_context_from_namespace(args)

    assert runtime_context.jp_sqlcipher_key_hex == "a" * 64


def test_runtime_context_ignores_jp_sqlcipher_key_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("_".join(("BA", "JP", "SQLCIPHER", "KEY", "HEX")), "b" * 64)

    runtime_context = AppSettings(region="jp").to_runtime_context()

    assert runtime_context.jp_sqlcipher_key_hex == ""


def test_cli_jp_sqlcipher_key_is_not_affected_by_environment(monkeypatch) -> None:
    monkeypatch.setenv("_".join(("BA", "JP", "SQLCIPHER", "KEY", "HEX")), "b" * 64)
    parser = build_parser()
    args = parser.parse_args(
        [
            "extract",
            "--region",
            "jp",
            "--jp-sqlcipher-key-hex",
            "c" * 64,
        ]
    )

    runtime_context = runtime_context_from_namespace(args)

    assert runtime_context.jp_sqlcipher_key_hex == "c" * 64


def test_extract_cli_accepts_search_options() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "extract",
            "--region",
            "jp",
            "--version",
            "1.70.436321",
            "--search",
            "Shiroko",
            "--advanced-search",
            "シロコ",
        ]
    )

    runtime_context = runtime_context_from_namespace(args)

    assert runtime_context.search == ("Shiroko",)
    assert runtime_context.advanced_search == ("シロコ",)


def test_cli_help_documents_relation_and_search_support() -> None:
    parser = build_parser()

    root_help = parser.format_help()

    assert "relation" in root_help
    assert "Character relation commands" in root_help

    subparsers_action = next(
        action
        for action in parser._actions
        if getattr(action, "dest", None) == "command"
    )
    choices = subparsers_action.choices

    relation_help = re.sub(r"\s+", " ", choices["relation"].format_help())
    sync_help = re.sub(r"\s+", " ", choices["sync"].format_help())
    extract_help = re.sub(r"\s+", " ", choices["extract"].format_help())

    assert "Build character relation file" in relation_help
    assert "Search assets by character relation fields (GL/JP sync only)." in sync_help
    assert (
        "Search existing raw assets by character relation fields (GL/JP extract only)."
        in extract_help
    )


def test_readmes_document_current_cli_search_and_relation_support() -> None:
    root = Path(__file__).resolve().parents[1]
    chinese_readme = (root / "README.md").read_text(encoding="utf-8")
    english_readme = (root / "docs" / "README.en.md").read_text(encoding="utf-8")

    for content in (chinese_readme, english_readme):
        assert "`ba-downloader relation build [options]`" in content
        assert "<!-- - `ba-downloader relation build [options]`" not in content
        assert (
            "`sync`、`download`、`extract`" in content
            or "`sync`, `download`, and `extract`" in content
        )
        assert "GL/JP" in content
        assert "CN" in content
        assert "extract -as" in content
        assert "relation build" in content

    assert "JP 不支持指定 `--version`" in chinese_readme
    assert "JP does not support specifying `--version`" in english_readme


def test_support_builders_create_common_runtime_and_assets(tmp_path: Path) -> None:
    context = build_runtime_context(
        tmp_path,
        region="gl",
        search=("Shiroko",),
        advanced_search=("cv=Ogura Yui",),
    )
    resources = build_asset_collection(
        ("Bundle/chara.bundle", AssetType.bundle),
        ("Media/voice.zip", AssetType.media, 10),
    )

    assert context.region == "gl"
    assert context.search == ("Shiroko",)
    assert context.advanced_search == ("cv=Ogura Yui",)
    assert [resource.path for resource in resources] == [
        "Bundle/chara.bundle",
        "Media/voice.zip",
    ]
    assert resources[1].size == 10
