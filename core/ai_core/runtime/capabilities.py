from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeCapabilities:
    can_run_application: bool
    can_run_local_llm: bool
    recommended_local_llm: bool
    max_parallel_tasks: int
    network_required_for_remote_ai: bool


class CapabilityEvaluator:
    """
    Converts detected hardware into safe runtime capabilities.

    The evaluator deliberately avoids binding the application to a
    particular CPU vendor, GPU vendor, or operating system.

    Supported hardware families include:
        - Intel
        - AMD
        - Apple Silicon
        - x86_64
        - ARM64

    The goal is graceful degradation rather than aggressive hardware
    requirements.
    """

    MIN_RAM_FOR_APPLICATION_GB = 4
    MIN_CPU_CORES_FOR_APPLICATION = 2

    MIN_RAM_FOR_LOCAL_LLM_GB = 16
    MIN_CPU_CORES_FOR_LOCAL_LLM = 4

    RECOMMENDED_RAM_FOR_LOCAL_LLM_GB = 24
    RECOMMENDED_CPU_CORES_FOR_LOCAL_LLM = 8

    def evaluate(self, hardware) -> RuntimeCapabilities:
        can_run_application = (
            hardware.cpu_cores
            >= self.MIN_CPU_CORES_FOR_APPLICATION
            and hardware.memory_gb
            >= self.MIN_RAM_FOR_APPLICATION_GB
        )

        can_run_local_llm = (
            hardware.cpu_cores
            >= self.MIN_CPU_CORES_FOR_LOCAL_LLM
            and hardware.memory_gb
            >= self.MIN_RAM_FOR_LOCAL_LLM_GB
        )

        recommended_local_llm = (
            can_run_local_llm
            and hardware.cpu_cores
            >= self.RECOMMENDED_CPU_CORES_FOR_LOCAL_LLM
            and hardware.memory_gb
            >= self.RECOMMENDED_RAM_FOR_LOCAL_LLM_GB
        )

        max_parallel_tasks = self._parallel_tasks(
            hardware.cpu_cores,
            hardware.memory_gb,
        )

        return RuntimeCapabilities(
            can_run_application=can_run_application,
            can_run_local_llm=can_run_local_llm,
            recommended_local_llm=recommended_local_llm,
            max_parallel_tasks=max_parallel_tasks,
            network_required_for_remote_ai=True,
        )

    @staticmethod
    def _parallel_tasks(
        cpu_cores: int,
        memory_gb: float,
    ) -> int:
        """
        Conservative concurrency policy.

        This is intentionally independent of CPU vendor.
        """

        if cpu_cores <= 2 or memory_gb < 8:
            return 1

        if cpu_cores <= 4 or memory_gb < 16:
            return 2

        if cpu_cores <= 8 or memory_gb < 32:
            return 4

        return 8
