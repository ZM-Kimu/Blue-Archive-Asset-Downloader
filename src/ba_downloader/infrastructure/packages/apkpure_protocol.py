from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_PROTOBUF_BYTES = 16 * 1024 * 1024
MAX_PROTOBUF_FIELDS = 100_000


class ApkPureProtocolError(ValueError):
    """Raised when the APKPure response does not match the expected wire schema."""


@dataclass(frozen=True, slots=True)
class ProtobufField:
    number: int
    wire_type: int
    value: int | bytes


@dataclass(frozen=True, slots=True)
class ApkPurePackageVariant:
    package_name: str
    version: str
    version_code: str
    package_format: str
    download_url: str
    release_timestamp: datetime | None


def decode_apkpure_variants(payload: bytes) -> tuple[ApkPurePackageVariant, ...]:
    root = _decode_message(payload, path="root")
    response = _required_message(root, 1, path="root.1")
    body = _required_message(
        _decode_message(response, path="root.1"),
        7,
        path="root.1.7",
    )
    body_message = _decode_message(body, path="root.1.7")

    variants: list[ApkPurePackageVariant] = []
    for section_index, section in enumerate(_bytes_fields(body_message, 2)):
        section_path = f"root.1.7.2[{section_index}]"
        section_message = _decode_message(section, path=section_path)
        section_name = _optional_text(section_message, 1, path=f"{section_path}.1")
        if section_name != "version_list":
            continue
        container = _required_message(
            section_message,
            3,
            path=f"{section_path}.3",
        )
        container_message = _decode_message(container, path=f"{section_path}.3")
        for record_index, record in enumerate(_bytes_fields(container_message, 2)):
            variants.append(
                _decode_release_record(
                    record,
                    path=f"{section_path}.3.2[{record_index}]",
                )
            )

    if not variants:
        raise ApkPureProtocolError(
            "APKPure response does not contain version_list release records."
        )
    return tuple(variants)


def _decode_release_record(payload: bytes, *, path: str) -> ApkPurePackageVariant:
    message = _decode_message(payload, path=path)
    download_payload = _required_message(message, 24, path=f"{path}.24")
    download_message = _decode_message(download_payload, path=f"{path}.24")
    timestamp_text = _optional_text(message, 36, path=f"{path}.36")
    timestamp: datetime | None = None
    if timestamp_text:
        try:
            timestamp = datetime.fromisoformat(timestamp_text)
        except ValueError as exc:
            raise ApkPureProtocolError(
                f"APKPure release timestamp is invalid at {path}.36."
            ) from exc

    return ApkPurePackageVariant(
        package_name=_required_text(message, 4, path=f"{path}.4"),
        version_code=_required_text(message, 5, path=f"{path}.5"),
        version=_required_text(message, 6, path=f"{path}.6"),
        package_format=_required_text(
            download_message,
            8,
            path=f"{path}.24.8",
        ),
        download_url=_required_text(
            download_message,
            9,
            path=f"{path}.24.9",
        ),
        release_timestamp=timestamp,
    )


def _decode_message(payload: bytes, *, path: str) -> tuple[ProtobufField, ...]:
    if len(payload) > MAX_PROTOBUF_BYTES:
        raise ApkPureProtocolError(
            f"APKPure protobuf message exceeds the size limit at {path}."
        )
    fields: list[ProtobufField] = []
    position = 0
    while position < len(payload):
        if len(fields) >= MAX_PROTOBUF_FIELDS:
            raise ApkPureProtocolError(
                f"APKPure protobuf message exceeds the field limit at {path}."
            )
        key, position = _read_varint(payload, position, path=path)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number == 0:
            raise ApkPureProtocolError(
                f"APKPure protobuf contains field number zero at {path}."
            )

        value: int | bytes
        if wire_type == 0:
            value, position = _read_varint(payload, position, path=path)
        elif wire_type == 1:
            value, position = _read_fixed(payload, position, 8, path=path)
        elif wire_type == 2:
            length, position = _read_varint(payload, position, path=path)
            value, position = _read_fixed(
                payload,
                position,
                length,
                path=path,
            )
        elif wire_type == 5:
            value, position = _read_fixed(payload, position, 4, path=path)
        else:
            raise ApkPureProtocolError(
                f"APKPure protobuf uses unsupported wire type {wire_type} at "
                f"{path}.{field_number}."
            )
        fields.append(
            ProtobufField(
                number=field_number,
                wire_type=wire_type,
                value=value,
            )
        )
    return tuple(fields)


def _read_varint(payload: bytes, position: int, *, path: str) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if position >= len(payload):
            raise ApkPureProtocolError(
                f"APKPure protobuf contains a truncated varint at {path}."
            )
        byte = payload[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, position
    raise ApkPureProtocolError(
        f"APKPure protobuf contains an oversized varint at {path}."
    )


def _read_fixed(
    payload: bytes,
    position: int,
    size: int,
    *,
    path: str,
) -> tuple[bytes, int]:
    end = position + size
    if size < 0 or end > len(payload):
        raise ApkPureProtocolError(
            f"APKPure protobuf field exceeds message bounds at {path}."
        )
    return payload[position:end], end


def _bytes_fields(
    fields: tuple[ProtobufField, ...],
    field_number: int,
) -> tuple[bytes, ...]:
    return tuple(
        field.value
        for field in fields
        if field.number == field_number
        and field.wire_type == 2
        and isinstance(field.value, bytes)
    )


def _required_message(
    fields: tuple[ProtobufField, ...],
    field_number: int,
    *,
    path: str,
) -> bytes:
    values = _bytes_fields(fields, field_number)
    if len(values) != 1:
        raise ApkPureProtocolError(
            f"APKPure protobuf requires exactly one message at {path}; "
            f"found {len(values)}."
        )
    return values[0]


def _required_text(
    fields: tuple[ProtobufField, ...],
    field_number: int,
    *,
    path: str,
) -> str:
    value = _optional_text(fields, field_number, path=path)
    if value is None or not value:
        raise ApkPureProtocolError(
            f"APKPure protobuf requires a non-empty string at {path}."
        )
    return value


def _optional_text(
    fields: tuple[ProtobufField, ...],
    field_number: int,
    *,
    path: str,
) -> str | None:
    values = _bytes_fields(fields, field_number)
    if not values:
        return None
    if len(values) != 1:
        raise ApkPureProtocolError(
            f"APKPure protobuf contains duplicate strings at {path}."
        )
    try:
        return values[0].decode("utf8")
    except UnicodeDecodeError as exc:
        raise ApkPureProtocolError(
            f"APKPure protobuf contains invalid UTF-8 at {path}."
        ) from exc
