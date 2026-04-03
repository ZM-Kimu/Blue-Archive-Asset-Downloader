from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.settings import AppSettings


def test_settings_normalization_defaults() -> None:
    settings = AppSettings(region="jp").normalized()

    assert settings.temp_dir == "JP_Android_Temp"
    assert settings.raw_dir == "JP_Android_RawData"
    assert settings.extract_dir == "JP_Android_Extracted"
    assert settings.platform == "android"
    assert settings.platform_explicit is False
    assert settings.resource_type == ("table", "media", "bundle")


def test_settings_normalization_uses_platform_specific_jp_directories() -> None:
    settings = AppSettings(region="jp", platform="windows", platform_explicit=True).normalized()

    assert settings.temp_dir == "JP_Windows_Temp"
    assert settings.raw_dir == "JP_Windows_RawData"
    assert settings.extract_dir == "JP_Windows_Extracted"
    assert settings.platform == "windows"
    assert settings.platform_explicit is True


def test_settings_normalization_keeps_non_jp_default_directories() -> None:
    settings = AppSettings(region="gl", platform="ios", platform_explicit=True).normalized()

    assert settings.temp_dir == "GLTemp"
    assert settings.raw_dir == "GLRawData"
    assert settings.extract_dir == "GLExtracted"


def test_runtime_context_copies_normalized_settings() -> None:
    runtime_context = RuntimeContext.from_settings(
        AppSettings(
            region="gl",
            threads=8,
            raw_dir="RawData",
            extract_dir="Extracted",
            temp_dir="Temp",
            resource_type=("media",),
            max_retries=2,
        ),
    )

    assert runtime_context.region == "gl"
    assert runtime_context.threads == 8
    assert runtime_context.resource_type == ("media",)
    assert runtime_context.max_threads == 56
    assert runtime_context.platform == "android"
    assert runtime_context.platform_explicit is False
