from dataclasses import asdict, dataclass
import os
import platform
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class HardwareInfo:
    platform: str
    architecture: str
    machine: str
    processor: str
    python_version: str
    cpu_cores: int
    memory_gb: float
    gpu_available: bool
    gpu_name: str | None


class HardwareDetector:
    """Detects host capabilities without requiring optional dependencies."""

    def detect(self) -> HardwareInfo:
        system = platform.system().lower()
        machine = platform.machine().lower()

        return HardwareInfo(
            platform=self._normalize_platform(system),
            architecture=self._normalize_architecture(machine),
            machine=machine,
            processor=platform.processor() or "unknown",
            python_version=platform.python_version(),
            cpu_cores=os.cpu_count() or 1,
            memory_gb=self._memory_gb(),
            gpu_available=self._gpu_available(system),
            gpu_name=self._gpu_name(system),
        )

    @staticmethod
    def _normalize_platform(system: str) -> str:
        if system == "darwin":
            return "macos"
        if system == "windows":
            return "windows"
        if system == "linux":
            return "linux"
        return system

    @staticmethod
    def _normalize_architecture(machine: str) -> str:
        if machine in {"x86_64", "amd64"}:
            return "x86_64"

        if machine in {
            "arm64",
            "aarch64",
        }:
            return "arm64"

        return machine

    @staticmethod
    def _memory_gb() -> float:
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round(
                pages * page_size / (1024 ** 3),
                2,
            )
        except (
            AttributeError,
            OSError,
            ValueError,
        ):
            pass

        if sys.platform == "win32":
            try:
                import ctypes

                class MemoryStatus(ctypes.Structure):
                    _fields_ = [
                        ("length", ctypes.c_ulong),
                        ("memory_load", ctypes.c_ulong),
                        ("total", ctypes.c_ulonglong),
                        ("available", ctypes.c_ulonglong),
                        ("total_page", ctypes.c_ulonglong),
                        ("available_page", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong),
                        ("available_virtual", ctypes.c_ulonglong),
                        ("available_extended", ctypes.c_ulonglong),
                    ]

                status = MemoryStatus()
                status.length = ctypes.sizeof(MemoryStatus)

                ctypes.windll.kernel32.GlobalMemoryStatusEx(
                    ctypes.byref(status)
                )

                return round(
                    status.total / (1024 ** 3),
                    2,
                )
            except Exception:
                pass

        return 0.0

    @staticmethod
    def _gpu_available(system: str) -> bool:
        if system == "darwin":
            return bool(
                shutil.which("system_profiler")
            )

        if system == "windows":
            return bool(
                shutil.which("nvidia-smi")
            )

        if system == "linux":
            return bool(
                shutil.which("nvidia-smi")
                or shutil.which("rocminfo")
            )

        return False

    @staticmethod
    def _gpu_name(system: str) -> str | None:
        if system == "darwin":
            command = [
                "system_profiler",
                "SPDisplaysDataType",
            ]
        elif system in {"windows", "linux"}:
            if not shutil.which("nvidia-smi"):
                return None

            command = [
                "nvidia-smi",
                "--query-gpu=name",
                "--format=csv,noheader",
            ]
        else:
            return None

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )

            output = result.stdout.strip()

            if not output:
                return None

            if system == "darwin":
                for line in output.splitlines():
                    if "Chipset Model:" in line:
                        return line.split(
                            "Chipset Model:",
                            1,
                        )[1].strip()

            return output.splitlines()[0].strip()

        except (
            OSError,
            subprocess.SubprocessError,
        ):
            return None

    def as_dict(self) -> dict:
        return asdict(self.detect())
