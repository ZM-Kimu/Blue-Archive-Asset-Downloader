from base64 import b64decode, b64encode
from struct import Struct
from typing import TypeVar, Union

from Crypto.Util.strxor import strxor
from xxhash import xxh32_intdigest

from utils.mersenne_twister import MersenneTwister

T = TypeVar("T", int, float)


def calculate_hash(name: Union[bytes, str]) -> int:
    """Calculate a hash using xxhash with UTF-8 encoding if needed."""
    if isinstance(name, str):
        name = name.encode("utf8")
    return xxh32_intdigest(name)


def new_zip_password(key: str) -> bytes:
    """Generate a new zip password based on a base64-encoded key."""
    return b64encode(create_key(key, 15))


def create_key(name: str, size: int = 8) -> bytes:
    """Create a random key based on a hashed name and a specific size."""
    seed = calculate_hash(name)
    return MersenneTwister(seed).next_bytes(size)


def xor_with_key(name: str, data: bytes) -> bytes:
    """XOR the data with a generated key based on the name."""
    if not data:
        return data
    mask = create_key(name, len(data))
    return xor(data, mask)


def xor(value: bytes, key: bytes) -> bytes:
    """XOR operation between two byte arrays."""
    if len(value) == len(key):
        return strxor(value, key)
    if len(value) < len(key):
        return strxor(value, key[: len(value)])
    # Handle the case where the value is longer than the key
    return b"".join(
        strxor(value[i : i + len(key)], key)
        for i in range(0, len(value) - len(key) + 1, len(key))
    ) + strxor(
        value[len(value) - len(value) % len(key) :], key[: len(value) % len(key)]
    )


def xor_struct(value: T, key: bytes, struct: Struct) -> T:
    """XOR operation with a structured binary format."""
    packed_value = struct.pack(value)
    return struct.unpack(xor(packed_value, key))[0]


def convert_sbyte(value: int, key: bytes) -> int:
    return xor_struct(value, key, Struct("<b")) if value else 0


def convert_int(value: int, key: bytes) -> int:
    return xor_struct(value, key, Struct("<i")) if value else 0


def convert_long(value: int, key: bytes) -> int:
    return xor_struct(value, key, Struct("<q")) if value else 0


def convert_uint(value: int, key: bytes) -> int:
    return xor_struct(value, key, Struct("<I")) if value else 0


def convert_ulong(value: int, key: bytes) -> int:
    return xor_struct(value, key, Struct("<Q")) if value else 0


def convert_float(value: float, key: bytes) -> float:
    return convert_int(int(value), key) * 0.00001 if value else 0.0


def convert_double(value: float, key: bytes) -> float:
    return convert_long(int(value), key) * 0.00001 if value else 0.0


def encrypt_float(value: float, key: bytes) -> float:
    return convert_int(int(value * 100000), key) if value else 0.0


def encrypt_double(value: float, key: bytes) -> float:
    return convert_long(int(value * 100000), key) if value else 0.0


def convert_string(value: Union[bytes, str], key: bytes) -> str:
    """Decrypt or decode a base64 string or raw bytes, depending on the input."""
    if not value:
        return ""

    if isinstance(value, str):
        value = value.encode("utf-8")

    try:
        raw = b64decode(value)
        return xor(raw, key).decode("utf16")
    except Exception:
        return value.decode("utf8")


def encrypt_string(value: str, key: bytes) -> Union[str, bytes]:
    """Encrypt a string using XOR and base64 encoding."""
    if not value or len(value) < 8:
        return value.encode() if value else b""

    raw = value.encode("utf16")
    return b64encode(xor(raw, key)).decode()
