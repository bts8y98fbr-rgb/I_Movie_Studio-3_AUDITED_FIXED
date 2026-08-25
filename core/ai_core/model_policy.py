from dataclasses import dataclass
from enum import Enum


class SelectionMode(Enum):
    FIXED = "fixed"
    PREFERRED = "preferred"
    AUTOMATIC = "automatic"


@dataclass
class ModelPolicy:
    provider: str | None = None
    model: str | None = None
    mode: SelectionMode = SelectionMode.AUTOMATIC
    approved_models: list[str] | None = None

    def allows(self, provider: str, model: str) -> bool:

        if self.mode == SelectionMode.FIXED:
            return (
                provider == self.provider
                and model == self.model
            )

        if self.mode == SelectionMode.PREFERRED:
            if self.approved_models is None:
                return False

            return model in self.approved_models

        if self.mode == SelectionMode.AUTOMATIC:
            return True

        return False
