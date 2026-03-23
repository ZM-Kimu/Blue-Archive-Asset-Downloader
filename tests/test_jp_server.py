import pytest

from ba_downloader.infrastructure.apk.package_manager import _resolve_filename
from ba_downloader.infrastructure.regions.providers.jp import JPServer


def test_parse_package_info_prefers_highest_version() -> None:
    payload = (
        b"com.YostarJP.BlueArchive\x00"
        b"1.64.123456\x00"
        b"https://download.pureapk.com/b/XAPK/old-build.xapk\x00"
        b"com.YostarJP.BlueArchive\x00"
        b"1.66.405117\x00"
        b"https://download.pureapk.com/b/XAPK/latest-build.xapk\x00"
    )

    package_info = JPServer.parse_package_info(payload)

    assert package_info.version == "1.66.405117"
    assert package_info.download_url == (
        "https://download.pureapk.com/b/XAPK/latest-build.xapk"
    )


def test_parse_package_info_raises_for_invalid_payload() -> None:
    with pytest.raises(LookupError, match="PureAPK"):
        JPServer.parse_package_info(b"invalid payload")


def test_resolve_filename_falls_back_to_url() -> None:
    file_name = _resolve_filename(
        "",
        "https://download.pureapk.com/b/XAPK/com.YostarJP.BlueArchive",
    )

    assert file_name == "com.YostarJP.BlueArchive.xapk"
