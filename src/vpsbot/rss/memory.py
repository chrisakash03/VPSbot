from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

USED_PAUSE_BYTES = 950 * 1024 * 1024
AVAILABLE_FLOOR_BYTES = 64 * 1024 * 1024
_warned_unreadable = False


@dataclass(frozen=True)
class HostMemory:
    total_bytes: int
    available_bytes: int

    @property
    def used_bytes(self) -> int:
        return max(0, self.total_bytes - self.available_bytes)


def parse_meminfo(text: str) -> HostMemory | None:
    total_kb: int | None = None
    available_kb: int | None = None
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            total_kb = _kibibytes(line)
        elif line.startswith("MemAvailable:"):
            available_kb = _kibibytes(line)
    if total_kb is None or available_kb is None:
        return None
    return HostMemory(total_bytes=total_kb * 1024, available_bytes=available_kb * 1024)


def memory_is_hot(mem: HostMemory) -> bool:
    return (
        mem.used_bytes >= USED_PAUSE_BYTES
        or mem.available_bytes < AVAILABLE_FLOOR_BYTES
    )


def read_host_memory(path: str = "/proc/meminfo") -> HostMemory | None:
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return None
    return parse_meminfo(text)


def host_memory_hot() -> bool:
    global _warned_unreadable
    mem = read_host_memory()
    if mem is None:
        if not _warned_unreadable:
            logger.warning("Could not read /proc/meminfo; excerpt fetches will continue")
            _warned_unreadable = True
        return False
    return memory_is_hot(mem)


def _kibibytes(line: str) -> int | None:
    parts = line.split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None
