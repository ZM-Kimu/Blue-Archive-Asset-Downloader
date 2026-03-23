from ba_downloader.domain.models.settings import AppSettings
from ba_downloader.utils.config import Config, apply_settings


def test_settings_normalization_defaults() -> None:
    settings = AppSettings(region="jp").normalized()

    assert settings.temp_dir == "JPTemp"
    assert settings.raw_dir == "JPRawData"
    assert settings.extract_dir == "JPExtracted"
    assert settings.resource_type == ("table", "media", "bundle")


def test_apply_settings_updates_runtime_config() -> None:
    normalized = apply_settings(
        AppSettings(
            region="gl",
            threads=8,
            raw_dir="RawData",
            extract_dir="Extracted",
            temp_dir="Temp",
            resource_type=("media",),
            max_retries=2,
        )
    )

    assert normalized.region == "gl"
    assert Config.region == "gl"
    assert Config.threads == 8
    assert Config.resource_type == ["media"]
    assert Config.max_threads == 56
