import math
import time
from typing import List


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
