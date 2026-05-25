from ba_downloader.application.config import AppSettings


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
    runtime_context = (
        AppSettings(
            region="gl",
            threads=8,
            raw_dir="RawData",
            extract_dir="Extracted",
            temp_dir="Temp",
            resource_type=("media",),
            max_retries=2,
        ).to_runtime_context()
    )

    assert runtime_context.region == "gl"
    assert runtime_context.threads == 8
    assert runtime_context.resource_type == ("media",)
    assert runtime_context.platform == "android"
    assert runtime_context.platform_explicit is False
