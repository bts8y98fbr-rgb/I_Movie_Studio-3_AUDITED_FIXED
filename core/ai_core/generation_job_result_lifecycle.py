from collections.abc import Mapping
from datetime import datetime, timezone
import json

from core.ai_core.generation_job_repository import (
    GenerationJobRepositoryError,
)


class GenerationJobResultLifecycleError(RuntimeError):
    """Raised when one remote result retrieval step is invalid."""


class GenerationJobResultLifecycle:
    SENSITIVE_KEYS = {
        "api_key",
        "apikey",
        "api_secret",
        "client_secret",
        "access_token",
        "refresh_token",
        "auth_token",
        "bearer_token",
        "password",
        "passwd",
        "credential",
        "credentials",
        "authorization",
    }

    IDENTITY_FIELDS = (
        "task_id",
        "task_type",
        "job_id",
        "provider",
        "metadata",
    )

    def __init__(
        self,
        job_repository,
        provider_resolver,
        audit=None,
        events=None,
    ):
        self.job_repository = job_repository
        self.provider_resolver = provider_resolver
        self.audit = audit
        self.events = events

    def retrieve_once(self, task_id):
        existing = self._load_existing_retrieved(
            task_id
        )
        if existing is not None:
            return existing

        receipt = self._load_submitted_receipt(
            task_id
        )
        terminal = self._load_terminal(
            task_id
        )

        self._validate_terminal_eligibility(
            terminal
        )
        self._validate_cross_record_identity(
            receipt,
            terminal,
        )

        provider_name = terminal["provider"]
        job_id = terminal["job_id"]

        provider = self.provider_resolver.get(
            provider_name
        )

        if provider is None:
            raise GenerationJobResultLifecycleError(
                f"Generation provider {provider_name!r} is unavailable"
            )

        resolved_name = getattr(
            provider,
            "name",
            None,
        )

        if resolved_name != provider_name:
            raise GenerationJobResultLifecycleError(
                "Generation provider identity mismatch: "
                f"terminal={provider_name!r}, "
                f"resolved={resolved_name!r}"
            )

        get_result = getattr(
            provider,
            "get_result",
            None,
        )

        if not callable(get_result):
            raise GenerationJobResultLifecycleError(
                f"Generation provider {provider_name!r} "
                "cannot retrieve job result"
            )

        try:
            response = get_result(job_id)
        except Exception as exc:
            raise GenerationJobResultLifecycleError(
                "Generation provider result retrieval failed: "
                f"provider={provider_name!r}, job_id={job_id!r}"
            ) from exc

        provider_result = self._snapshot_provider_result(
            response,
            provider_name,
            job_id,
        )

        retrieved = {
            "format_version":
                self.job_repository.FORMAT_VERSION,
            "task_id":
                terminal["task_id"],
            "task_type":
                terminal["task_type"],
            "job_id":
                job_id,
            "provider":
                provider_name,
            "metadata":
                dict(terminal["metadata"]),
            "result_state":
                "retrieved",
            "asset_ready":
                False,
            "provider_result":
                provider_result,
            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }

        durable = self._persist_retrieved(
            retrieved
        )
        self._record_observability(
            durable
        )

        return durable

    def _load_existing_retrieved(
        self,
        task_id,
    ):
        try:
            if not self.job_repository.retrieved_exists(
                task_id
            ):
                return None

            return self.job_repository.load_retrieved(
                task_id
            )
        except GenerationJobRepositoryError as exc:
            raise GenerationJobResultLifecycleError(
                "Cannot load retrieved generation job result: "
                f"{exc}"
            ) from exc

    def _load_submitted_receipt(
        self,
        task_id,
    ):
        try:
            return self.job_repository.resume(
                task_id
            )
        except GenerationJobRepositoryError as exc:
            raise GenerationJobResultLifecycleError(
                "Invalid submitted generation job receipt: "
                f"{exc}"
            ) from exc

    def _load_terminal(
        self,
        task_id,
    ):
        try:
            if not self.job_repository.terminal_exists(
                task_id
            ):
                raise GenerationJobResultLifecycleError(
                    "Successful terminal generation job record "
                    "is required before result retrieval"
                )

            return self.job_repository.load_terminal(
                task_id
            )
        except GenerationJobResultLifecycleError:
            raise
        except GenerationJobRepositoryError as exc:
            raise GenerationJobResultLifecycleError(
                "Invalid terminal generation job record: "
                f"{exc}"
            ) from exc

    def _validate_terminal_eligibility(
        self,
        terminal,
    ):
        status = terminal.get("status")

        if status != "succeeded":
            raise GenerationJobResultLifecycleError(
                "Generation job is not eligible for result retrieval: "
                f"terminal status={status!r}"
            )

        if (
            terminal.get("result_state")
            != "pending_retrieval"
            or terminal.get("asset_ready") is not False
        ):
            raise GenerationJobResultLifecycleError(
                "Successful generation job is not in "
                "pending_retrieval state"
            )

    def _validate_cross_record_identity(
        self,
        receipt,
        terminal,
    ):
        for field in self.IDENTITY_FIELDS:
            if receipt.get(field) != terminal.get(
                field
            ):
                raise GenerationJobResultLifecycleError(
                    "Submitted/terminal generation job "
                    "identity mismatch: "
                    f"field={field!r}, "
                    f"submitted={receipt.get(field)!r}, "
                    f"terminal={terminal.get(field)!r}"
                )

    def _snapshot_provider_result(
        self,
        response,
        provider_name,
        job_id,
    ):
        if (
            not isinstance(response, Mapping)
            or not response
        ):
            raise GenerationJobResultLifecycleError(
                "Generation provider result must be a "
                "non-empty mapping"
            )

        if (
            "job_id" in response
            and response["job_id"] != job_id
        ):
            raise GenerationJobResultLifecycleError(
                "Generation result job identity mismatch: "
                f"expected={job_id!r}, "
                f"received={response['job_id']!r}"
            )

        if (
            "provider" in response
            and response["provider"]
            != provider_name
        ):
            raise GenerationJobResultLifecycleError(
                "Generation result provider identity mismatch: "
                f"expected={provider_name!r}, "
                f"received={response['provider']!r}"
            )

        try:
            candidate = dict(response)
        except Exception as exc:
            raise GenerationJobResultLifecycleError(
                "Generation provider result cannot be "
                "snapshotted as a dictionary"
            ) from exc

        if self._contains_sensitive_data(
            candidate
        ):
            raise GenerationJobResultLifecycleError(
                "Generation provider result contains "
                "credentials or sensitive authorization data"
            )

        try:
            serialized = json.dumps(
                candidate,
                ensure_ascii=False,
                allow_nan=False,
            )
            snapshot = json.loads(
                serialized
            )
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise GenerationJobResultLifecycleError(
                "Generation provider result must be "
                "JSON serializable"
            ) from exc

        if not isinstance(snapshot, dict) or not snapshot:
            raise GenerationJobResultLifecycleError(
                "Generation provider result snapshot must be "
                "a non-empty dictionary"
            )

        return snapshot

    def _contains_sensitive_data(
        self,
        value,
    ):
        if isinstance(value, Mapping):
            for key, nested in value.items():
                normalized = (
                    str(key)
                    .strip()
                    .lower()
                    .replace("-", "_")
                    .replace(" ", "_")
                )

                if normalized in self.SENSITIVE_KEYS:
                    return True

                if self._contains_sensitive_data(
                    nested
                ):
                    return True

            return False

        if isinstance(value, (list, tuple)):
            return any(
                self._contains_sensitive_data(
                    item
                )
                for item in value
            )

        return False

    def _persist_retrieved(
        self,
        retrieved,
    ):
        try:
            return self.job_repository.persist_retrieved(
                retrieved
            )
        except GenerationJobRepositoryError as exc:
            raise GenerationJobResultLifecycleError(
                "Cannot persist durable retrieved generation "
                f"job result: {exc}"
            ) from exc

    def _record_observability(
        self,
        retrieved,
    ):
        if self.audit is not None:
            try:
                self.audit.record(
                    "generation_job_result_retrieved",
                    dict(retrieved),
                )
            except Exception:
                pass

        if self.events is not None:
            try:
                self.events.emit(
                    "generation_job_result_retrieved",
                    dict(retrieved),
                )
            except Exception:
                pass
