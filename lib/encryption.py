"""Main encryption lib for encrypt."""

import hashlib
import math
import time
from base64 import b64decode, b64encode
from binascii import crc32
from struct import Struct
from typing import TypeVar

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from Crypto.Util.strxor import strxor
from xxhash import xxh32_intdigest, xxh64_intdigest

T = TypeVar("T", int, float)

SHORT = Struct("<h")
USHORT = Struct("<H")
INT = Struct("<i")
UINT = Struct("<I")
LONG = Struct("<q")
ULONG = Struct("<Q")
FLOAT = Struct("<f")
DOUBLE = Struct("<d")

AES_BLOCK_SIZE = 128 // 8
AES_KEY_SIZE = 128 // 8
PBKDF2_DERIVATION_ITERATIONS = 1000


def calculate_hash(name: bytes | str) -> int:
    """Calculate a 32-bit hash using xxhash with UTF-8 encoding if needed."""
    if isinstance(name, str):
        name = name.encode("utf8")
    return xxh32_intdigest(name)


def calculate_hash64(name: bytes | str) -> int:
    """Calculate a 64-bit hash using xxhash with UTF-8 encoding if needed."""
    if isinstance(name, str):
        name = name.encode("utf8")
    return xxh64_intdigest(name)


def calculate_crc(path: str) -> int:
    """Calculate the crc checksum value of a file.
    Args:
        path (str): File path.
    Returns:
        int: Crc checksum.
    """
    with open(path, "rb") as f:
        return crc32(f.read()) & 0xFFFFFFFF


def calculate_md5(path: str) -> str:
    """Calculate the md5 checksum value of a file.
    Args:
        path (str): File path.
    Returns:
        str: MD5 checksum.
    """
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def zip_password(key: str) -> bytes:
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


def convert_short(value: int, key: bytes = b"") -> int:
    """Convert value to short type using XOR encryption if a key is provided."""
    return xor_struct(value, key, SHORT) if value and key else value


def convert_ushort(value: int, key: bytes = b"") -> int:
    """Convert value to unsigned short type using XOR encryption if a key is provided."""
    return xor_struct(value, key, USHORT) if value and key else value


def convert_int(value: int, key: bytes = b"") -> int:
    """Convert value to int type using XOR encryption if a key is provided."""
    return xor_struct(value, key, INT) if value and key else value


def convert_uint(value: int, key: bytes = b"") -> int:
    """Convert value to unsigned int type using XOR encryption if a key is provided."""
    return xor_struct(value, key, UINT) if value and key else value


def convert_long(value: int, key: bytes = b"") -> int:
    """Convert value to long type using XOR encryption if a key is provided."""
    return xor_struct(value, key, LONG) if value and key else value


def convert_ulong(value: int, key: bytes = b"") -> int:
    """Convert value to unsigned long type using XOR encryption if a key is provided."""
    return xor_struct(value, key, ULONG) if value and key else value


def convert_float(value: float, key: bytes = b"") -> float:
    """Convert value to float type using XOR encryption if a key is provided."""
    return (convert_int(int(value), key) * 0.00001 if value else 0.0) if key else value


def convert_double(value: float, key: bytes = b"") -> float:
    """Convert value to double type using XOR encryption if a key is provided."""
    return (convert_long(int(value), key) * 0.00001 if value else 0.0) if key else value


def encrypt_float(value: float, key: bytes = b"") -> float:
    """Encrypt float value to integer-like format using XOR if a key is provided."""
    return (convert_int(int(value * 100000), key) if value else 0.0) if key else value


def encrypt_double(value: float, key: bytes = b"") -> float:
    """Encrypt double value to integer-like format using XOR if a key is provided."""
    return (convert_long(int(value * 100000), key) if value else 0.0) if key else value


def convert_string(value: bytes | str, key: bytes = b"") -> str:
    """Decrypt or decode a base64 string or raw bytes, depending on the input."""
    if not value:
        return ""

    try:
        raw = b64decode(value)
        if decoded := xor(raw, key).decode("utf16"):
            return decoded
        raise UnicodeError
    except:
        if isinstance(value, bytes):
            return value.decode("utf8")

    return ""


def encrypt_string(value: str, key: bytes) -> str | bytes:
    """Encrypt a string using XOR and base64 encoding."""
    if not value or len(value) < 8:
        return value.encode() if value else b""

    raw = value.encode("utf16")
    return b64encode(xor(raw, key)).decode()


def aes_encrypt(plain_text: str, encrypt_phrase: str) -> str:
    """Encrypts a plain text string using AES encryption (CBC mode) with a passphrase.

    Args:
        plain_text (str): The text to be encrypted.
        encrypt_phrase (str): The phrase used to derive the encryption key.

    Returns:
        str: A Base64-encoded string containing the salt, IV, and encrypted data.
    """
    salt = get_random_bytes(AES_KEY_SIZE)  # Key random salt .
    iv = get_random_bytes(AES_BLOCK_SIZE)  # Initialize aes block vector.

    derived = PBKDF2(
        encrypt_phrase, salt, AES_KEY_SIZE, count=PBKDF2_DERIVATION_ITERATIONS
    )
    cipher = AES.new(key=derived[:AES_KEY_SIZE], iv=iv, mode=AES.MODE_CBC)
    data = pad(cipher.encrypt(plain_text.encode("utf8")), AES_BLOCK_SIZE, style="pkcs7")
    return b64encode(salt + iv + data).decode("utf8")


def aes_decrypt(cipher_text: str | bytes, encrypt_phrase: str) -> str:
    """Decrypts a Base64-encoded AES-encrypted string back to its original plain text.


    Args:
        cipher_text (str): The Base64-encoded string containing the salt, IV, and encrypted data.
        encrypt_phrase (str): The phrase used to derive the encryption key (must match encryption phrase).

    Returns:
        str: The decrypted plain text.
    """
    raw_cipher = b64decode(cipher_text)
    salt = raw_cipher[:AES_KEY_SIZE]
    iv = raw_cipher[AES_KEY_SIZE : AES_KEY_SIZE + AES_BLOCK_SIZE]
    raw_cipher = raw_cipher[AES_KEY_SIZE + AES_BLOCK_SIZE :]

    derived = PBKDF2(
        encrypt_phrase, salt, AES_KEY_SIZE, count=PBKDF2_DERIVATION_ITERATIONS
    )
    cipher = AES.new(key=derived[:AES_KEY_SIZE], iv=iv, mode=AES.MODE_CBC)
    return unpad(cipher.decrypt(raw_cipher), AES_BLOCK_SIZE, style="pkcs7").decode(
        "utf-8"
    )


class MersenneTwister:
    # Constants for the Mersenne Twister algorithm
    N = 624
    M = 397
    MATRIX_A = 0x9908B0DF  # Constant vector a
    UPPER_MASK = 0x80000000  # Most significant w-r bits
    LOWER_MASK = 0x7FFFFFFF  # Least significant r bits

    def __init__(self, seed: int | None = None) -> None:
        if seed is None:
            seed = int(time.time() * 1000)  # Use current time in milliseconds as seed
        self.mt = [0] * self.N  # Create an array to store the state
        self.mti = self.N + 1  # Initial value for mti
        self.init_genrand(seed)

    def init_genrand(self, seed: int) -> None:
        """Initializes the generator with a seed."""
        self.mt[0] = seed & 0xFFFFFFFF  # Seed is limited to 32 bits
        for i in range(1, self.N):
            self.mt[i] = (
                1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i
            ) & 0xFFFFFFFF
        self.mti = self.N

    def _generate_numbers(self) -> None:
        """Generates N words at a time."""
        for i in range(self.N - self.M):
            y = (self.mt[i] & self.UPPER_MASK) | (self.mt[i + 1] & self.LOWER_MASK)
            self.mt[i] = (
                self.mt[i + self.M] ^ (y >> 1) ^ (self.MATRIX_A if y % 2 else 0)
            )
        for i in range(self.N - self.M, self.N - 1):
            y = (self.mt[i] & self.UPPER_MASK) | (self.mt[i + 1] & self.LOWER_MASK)
            self.mt[i] = (
                self.mt[i + (self.M - self.N)]
                ^ (y >> 1)
                ^ (self.MATRIX_A if y % 2 else 0)
            )
        y = (self.mt[self.N - 1] & self.UPPER_MASK) | (self.mt[0] & self.LOWER_MASK)
        self.mt[self.N - 1] = (
            self.mt[self.M - 1] ^ (y >> 1) ^ (self.MATRIX_A if y % 2 else 0)
        )
        self.mti = 0

    def genrand_int32(self) -> int:
        """Generates a random number on [0, 0xFFFFFFFF]-interval."""
        if self.mti >= self.N:
            self._generate_numbers()

        y = self.mt[self.mti]
        self.mti += 1

        # Tempering transformation
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18

        return y & 0xFFFFFFFF  # Return 32-bit unsigned integer

    def genrand_int31(self) -> int:
        """Generates a random number on [0, 0x7FFFFFFF]-interval."""
        return self.genrand_int32() >> 1

    def next_int(self, min_value: int = 0, max_value: int | None = None) -> int:
        """Generates a random integer between min_value and max_value."""
        if max_value is None:
            return self.genrand_int31()
        if min_value > max_value:
            raise ValueError("min_value must be less than or equal to max_value")
        return int(
            math.floor((max_value - min_value + 1) * self.genrand_real1() + min_value)
        )

    def genrand_real1(self) -> float:
        """Generates a random floating point number on [0,1]-interval."""
        return self.genrand_int32() * (1.0 / 4294967295.0)

    def genrand_real2(self) -> float:
        """Generates a random floating point number on [0,1)-interval."""
        return self.genrand_int32() * (1.0 / 4294967296.0)

    def genrand_real3(self) -> float:
        """Generates a random floating point number on (0,1)-interval."""
        return (self.genrand_int32() + 0.5) * (1.0 / 4294967296.0)

    def next_bytes(self, length: int) -> bytes:
        """Generates random bytes."""
        return b"".join(
            self.genrand_int31().to_bytes(4, "little", signed=False)
            for _ in range(0, length, 4)
        )[:length]

    def next_float(self, include_one: bool = False) -> float:
        """Generates a random floating-point number."""
        if include_one:
            return self.genrand_real1()
        return self.genrand_real2()

    def next_double(self, include_one: bool = False) -> float:
        """Generates a random double number."""
        return self.genrand_real1() if include_one else self.genrand_real2()

    def next_53bit_res(self) -> float:
        """Generates a random number with 53-bit resolution."""
        a = self.genrand_int32() >> 5
        b = self.genrand_int32() >> 6
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0)
