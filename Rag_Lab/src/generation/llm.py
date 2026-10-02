from abc import ABC, abstractmethod
from dataclasses import dataclass

from google import genai
from groq import Groq

from src.config import settings


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str


class BaseLLM(ABC):

    def __init__(
        self,
        model_name: str,
    ) -> None:
        self.model_name = model_name

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:
        raise NotImplementedError


class GeminiLLM(BaseLLM):

    def __init__(
        self,
        model_name: str,
    ) -> None:
        super().__init__(
            model_name
        )

        self.max_output_tokens = (
            settings.llm_max_output_tokens
        )

        self._client = None

    @property
    def client(self):

        if self._client is None:

            if not settings.gemini_api_key:
                raise ValueError(
                    "GEMINI_API_KEY "
                    "is not configured."
                )

            print(
                "[LLM] Initializing "
                "Gemini client..."
            )

            self._client = genai.Client(
                api_key=(
                    settings.gemini_api_key
                )
            )

        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:

        if not user_prompt.strip():
            raise ValueError(
                "User prompt cannot be empty."
            )

        print(
            f"[LLM] Gemini / "
            f"{self.model_name}"
        )

        try:
            interaction = (
                self.client
                .interactions
                .create(
                    model=(
                        self.model_name
                    ),
                    system_instruction=(
                        system_prompt
                    ),
                    input=(
                        user_prompt
                    ),
                    store=False,
                    generation_config={
                        "max_output_tokens": (
                            self.max_output_tokens
                        ),
                    },
                )
            )

        except Exception as exc:
            raise RuntimeError(
                "Gemini API request failed: "
                f"{exc}"
            ) from exc

        text = (
            interaction.output_text
            or ""
        ).strip()

        if not text:
            raise RuntimeError(
                "Gemini returned "
                "an empty response."
            )

        return LLMResponse(
            text=text,
            provider="gemini",
            model=self.model_name,
        )


class GroqLLM(BaseLLM):

    def __init__(
        self,
        model_name: str,
    ) -> None:
        super().__init__(
            model_name
        )

        self.max_output_tokens = (
            settings.llm_max_output_tokens
        )

        self._client = None

    @property
    def client(self):

        if self._client is None:

            if not settings.groq_api_key:
                raise ValueError(
                    "GROQ_API_KEY "
                    "is not configured."
                )

            print(
                "[LLM] Initializing "
                "Groq client..."
            )

            self._client = Groq(
                api_key=(
                    settings.groq_api_key
                )
            )

        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:

        if not user_prompt.strip():
            raise ValueError(
                "User prompt cannot be empty."
            )

        print(
            f"[LLM] Groq / "
            f"{self.model_name}"
        )

        try:
            completion = (
                self.client
                .chat
                .completions
                .create(
                    model=(
                        self.model_name
                    ),
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                system_prompt
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                user_prompt
                            ),
                        },
                    ],
                    max_completion_tokens=(
                        self.max_output_tokens
                    ),
                    temperature=0.3,
                    stream=False,
                )
            )

        except Exception as exc:
            raise RuntimeError(
                "Groq API request failed: "
                f"{exc}"
            ) from exc

        text = (
            completion
            .choices[0]
            .message
            .content
            or ""
        ).strip()

        if not text:
            raise RuntimeError(
                "Groq returned "
                "an empty response."
            )

        return LLMResponse(
            text=text,
            provider="groq",
            model=self.model_name,
        )


def _parse_models(
    value: str,
) -> list[str]:

    result = []

    for model in value.split(","):

        model = model.strip()

        if (
            model
            and model not in result
        ):
            result.append(
                model
            )

    return result


def get_llm_catalog(
) -> dict[str, list[str]]:

    gemini_models = (
        _parse_models(
            settings.gemini_models
        )
    )

    groq_models = (
        _parse_models(
            settings.groq_models
        )
    )

    if (
        settings.gemini_model
        not in gemini_models
    ):
        gemini_models.insert(
            0,
            settings.gemini_model,
        )

    if (
        settings.groq_model
        not in groq_models
    ):
        groq_models.insert(
            0,
            settings.groq_model,
        )

    return {
        "gemini": gemini_models,
        "groq": groq_models,
    }


class LLMManager:

    def __init__(self) -> None:
        self._instances: dict[
            tuple[str, str],
            BaseLLM,
        ] = {}

    def get_default_model(
        self,
        provider: str,
    ) -> str:

        if provider == "gemini":
            return settings.gemini_model

        if provider == "groq":
            return settings.groq_model

        raise ValueError(
            f"Unsupported provider: "
            f"{provider}"
        )

    def get(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> BaseLLM:

        provider = (
            provider
            or settings.llm_provider
        )

        provider = (
            provider
            .strip()
            .lower()
        )

        if not model:
            model = (
                self.get_default_model(
                    provider
                )
            )

        model = model.strip()

        catalog = (
            get_llm_catalog()
        )

        if provider not in catalog:
            raise ValueError(
                f"Unsupported LLM provider: "
                f"{provider}"
            )

        if model not in catalog[provider]:
            raise ValueError(
                f"Model '{model}' "
                f"is not configured for "
                f"provider '{provider}'."
            )

        key = (
            provider,
            model,
        )

        existing = (
            self._instances.get(
                key
            )
        )

        if existing is not None:
            return existing

        if provider == "gemini":

            instance = GeminiLLM(
                model_name=model
            )

        elif provider == "groq":

            instance = GroqLLM(
                model_name=model
            )

        else:
            raise ValueError(
                f"Unsupported provider: "
                f"{provider}"
            )

        self._instances[
            key
        ] = instance

        return instance

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:

        instance = self.get(
            provider=provider,
            model=model,
        )

        return instance.generate(
            system_prompt=(
                system_prompt
            ),
            user_prompt=(
                user_prompt
            ),
        )


llm_manager = LLMManager()