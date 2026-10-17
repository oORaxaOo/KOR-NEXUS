"""Provider-neutral AI contract. The default implementation is deliberately offline and disabled."""
from __future__ import annotations


class AIUnavailableError(RuntimeError):
    """Raised when a caller requests generation without an active provider."""


class AIProvider:
    """Small interface implemented by optional AI backends such as a future llama.cpp adapter."""

    def status(self):
        raise NotImplementedError

    def generate(self, prompt, context=None):
        raise NotImplementedError

    def close(self):
        return None


class DisabledAIProvider(AIProvider):
    """Safe default: no model, network access, background process, or implicit generation."""

    def status(self):
        return {
            'provider': 'disabled',
            'enabled': False,
            'available': False,
            'model_loaded': False,
            'reason': 'Kein KI-Provider konfiguriert; der Kern funktioniert vollständig ohne LLM.',
        }

    def generate(self, prompt, context=None):
        raise AIUnavailableError('KI ist deaktiviert. KOR-NEXUS bleibt ohne KI vollständig nutzbar.')
