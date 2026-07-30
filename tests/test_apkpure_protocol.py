import pytest

from ba_downloader.infrastructure.packages.apkpure_protocol import (
    ApkPureProtocolError,
    decode_apkpure_variants,
)

PACKAGE_NAME = "com.nexon.bluearchive"


@pytest.mark.parametrize(
    "payload",
    [
        b"\x0a\x80",
        b"\x0a\x05abc",
        b"\x00",
    ],
)
def test_apkpure_protocol_rejects_malformed_payload(payload: bytes) -> None:
    with pytest.raises(ApkPureProtocolError):
        decode_apkpure_variants(payload)
