from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("memory_load", wintypes.DWORD),
        ("total_physical", ctypes.c_ulonglong),
        ("available_physical", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong),
        ("available_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong),
        ("available_virtual", ctypes.c_ulonglong),
        ("available_extended_virtual", ctypes.c_ulonglong),
    ]


class SystemMemoryProbe:
    def total_physical_memory(self) -> int | None:
        try:
            if os.name == "nt":
                return self._windows_total_physical_memory()
            return self._posix_total_physical_memory()
        except (AttributeError, OSError, OverflowError, TypeError, ValueError):
            return None

    @staticmethod
    def _windows_total_physical_memory() -> int | None:
        status = _MemoryStatusEx()
        status.length = ctypes.sizeof(_MemoryStatusEx)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        query = kernel32.GlobalMemoryStatusEx
        query.argtypes = [ctypes.POINTER(_MemoryStatusEx)]
        query.restype = wintypes.BOOL
        if not query(ctypes.byref(status)):
            return None
        return int(status.total_physical)

    @staticmethod
    def _posix_total_physical_memory() -> int | None:
        sysconf = getattr(os, "sysconf", None)
        if not callable(sysconf):
            return None
        pages = sysconf("SC_PHYS_PAGES")
        page_size = sysconf("SC_PAGE_SIZE")
        if not isinstance(pages, int) or not isinstance(page_size, int):
            return None
        if pages <= 0 or page_size <= 0:
            return None
        return pages * page_size
