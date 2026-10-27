from llm.base import BaseLLM
from llm.config import LLMConfig


def create_llm(config: LLMConfig) -> BaseLLM:
    """Tworzy klienta na podstawie config.provider.
    Importy są leniwe: torch ładuje się tylko dla providera "local"."""
    if config.provider == "openrouter":
        from llm.openrouter import LLMService
    elif config.provider == "ollama":
        from llm.ollama import LLMService
    elif config.provider == "local":
        from llm.local import LLMService
    else:
        raise ValueError(f"Nieznany provider: {config.provider!r}")
    return LLMService(config)
