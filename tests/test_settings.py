from ba_downloader.domain.models.runtime import RuntimeContext
from ba_downloader.domain.models.settings import AppSettings


def test_settings_normalization_defaults() -> None:
    settings = AppSettings(region="jp").normalized()

    assert settings.temp_dir == "JPTemp"
    assert settings.raw_dir == "JPRawData"
    assert settings.extract_dir == "JPExtracted"
    assert settings.resource_type == ("table", "media", "bundle")


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
