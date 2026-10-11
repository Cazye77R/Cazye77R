"""StockMind – LLM Provider ABC."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def health(self) -> bool:
        """Prüft ob der Provider erreichbar/konfiguriert ist."""
        ...

    @abstractmethod
    def get_status(self) -> dict:
        """Erweiterter Status-Dict mit keys: running, url, model_count, error, install_guide."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Verfügbare Modell-Namen."""
        ...

    @abstractmethod
    def list_models_with_info(self) -> list[dict]:
        """Modell-Infos: name, size_gb, modified, description."""
        ...

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.2,
        **kwargs: object,
    ) -> str:
        """Sendet eine Nachrichtenliste an den Provider, gibt Antwort zurück."""
        ...

    def query(
        self,
        model: str,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> str:
        """Convenience-Wrapper: baut messages-Liste und ruft chat() auf."""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, model=model, temperature=temperature)
