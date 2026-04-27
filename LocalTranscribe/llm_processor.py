"""
LLM post-processing via a local Ollama instance.

Sends transcription text to an Ollama model for tasks such as
summarisation, cleanup, action-item extraction, and Q&A.
"""

# TODO: import requests
# TODO: import config constant OLLAMA_BASE_URL


class LLMProcessor:
    """Sends prompts to Ollama and returns generated text."""

    def __init__(self, base_url: str = None, model: str = "llama3"):
        """
        Initialize the Ollama client.

        Args:
            base_url: Ollama API base URL; falls back to config default.
            model: Ollama model tag to use (e.g. "llama3", "mistral").
        """
        # TODO: fall back to OLLAMA_BASE_URL from config when base_url is None
        # TODO: store base_url and model as instance attributes
        pass

    def _post(self, prompt: str) -> str:
        """
        Send a prompt to the Ollama /api/generate endpoint.

        Args:
            prompt: Full prompt string to send.

        Returns:
            Model-generated response text.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        # TODO: POST to {base_url}/api/generate with {"model": ..., "prompt": ..., "stream": False}
        # TODO: raise_for_status() and return response JSON "response" field
        pass

    def summarize(self, transcript: str) -> str:
        """
        Produce a concise summary of the transcript.

        Args:
            transcript: Full transcription text.

        Returns:
            Summary string.
        """
        # TODO: build German summarisation prompt
        # TODO: call self._post() and return result
        pass

    def extract_action_items(self, transcript: str) -> str:
        """
        Extract action items and decisions from the transcript.

        Args:
            transcript: Full transcription text.

        Returns:
            Bullet-point list of action items as a string.
        """
        # TODO: build German action-item extraction prompt
        # TODO: call self._post() and return result
        pass

    def answer_question(self, transcript: str, question: str) -> str:
        """
        Answer an arbitrary question about the transcript.

        Args:
            transcript: Full transcription text.
            question: User question string.

        Returns:
            Answer string grounded in the transcript.
        """
        # TODO: build German Q&A prompt combining transcript and question
        # TODO: call self._post() and return result
        pass
