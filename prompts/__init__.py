"""Wersjonowane prompty. Każda wersja to osobny plik v<N>.py; historia zmian w CHANGELOG.md."""
import importlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptVersion:
    version: str
    system: str
    template: str
    summary: str

    def render(self, ruling_text: str) -> str:
        # .replace zamiast .format, bo szablon zawiera klamry JSON-a
        return self.template.replace("{ruling_text}", ruling_text)


def list_versions() -> list[str]:
    files = Path(__file__).resolve().parent.glob("v[0-9]*.py")
    return sorted((f.stem for f in files), key=lambda v: int(v[1:]))


def get_prompt(version: str) -> PromptVersion:
    if version not in list_versions():
        raise ValueError(f"Nieznana wersja promptu {version!r}. Dostępne: {', '.join(list_versions())}")
    module = importlib.import_module(f"prompts.{version}")
    return PromptVersion(
        version=version,
        system=module.SYSTEM_PROMPT,
        template=module.RULING_EXTRACTION_TEMPLATE,
        summary=getattr(module, "SUMMARY", ""),
    )
