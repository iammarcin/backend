"""Google Gemini Veo 3.1 Fast video generation provider."""

from __future__ import annotations

import logging
from typing import Any, Optional

from google.genai import types  # type: ignore

from config.video.providers import gemini as gemini_config
from core.clients.ai import get_google_client
from core.exceptions import ProviderError, ValidationError
from core.providers.capabilities import ProviderCapabilities
from core.providers.base import BaseVideoProvider
from .utils.gemini import assets, options
from .utils.gemini import operations as operations_utils
from .utils.gemini import requests as request_utils
from .utils.gemini import sources as source_utils

logger = logging.getLogger(__name__)


class GeminiVideoProvider(BaseVideoProvider):
    """Video generation using Google's Gemini Veo 3.1 Fast models."""

    def __init__(self) -> None:
        self.client = get_google_client()
        if not self.client:
            raise ProviderError("Gemini client not initialized", provider="gemini_video")

        self.capabilities = ProviderCapabilities(
            streaming=False,
            image_to_video=True,
        )
        self.provider_name = "gemini"

        self.model = gemini_config.DEFAULT_MODEL
        self._model_aliases = gemini_config.MODEL_ALIASES
        self.available_aspect_ratios = set(gemini_config.AVAILABLE_ASPECT_RATIOS)
        self.available_person_generation = set(gemini_config.AVAILABLE_PERSON_GENERATION)
        self.available_resolutions = set(gemini_config.AVAILABLE_RESOLUTIONS)
        self.available_reference_types = {
            key: getattr(types.VideoGenerationReferenceType, value.upper(), types.VideoGenerationReferenceType.ASSET)
            for key, value in gemini_config.REFERENCE_TYPES.items()
        }
        self.poll_interval_seconds = gemini_config.POLL_INTERVAL_SECONDS
        self.timeout_seconds = gemini_config.TIMEOUT_SECONDS

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate a video from a text prompt."""

        if not prompt or not prompt.strip():
            raise ProviderError("Prompt cannot be empty", provider="gemini_video")

        model_name = self._resolve_model_name(model)
        generation_request = await request_utils.build_generation_request(
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            kwargs=kwargs,
            number_of_videos=options.resolve_number_of_videos(
                kwargs.get("number_of_videos", 1)
            ),
            available_aspect_ratios=self.available_aspect_ratios,
            available_person_generation=self.available_person_generation,
            available_resolutions=self.available_resolutions,
            prepare_image=self._prepare_image,
            resolve_reference_type=self._resolve_reference_type,
            default_aspect_ratio="16:9",
        )

        logger.info(
            "Generating Gemini video: model=%s duration=%ss aspect_ratio=%s",
            model_name,
            generation_request.duration,
            generation_request.aspect_ratio,
        )

        try:
            video_bytes = await operations_utils.execute_generation(
                self.client,
                prompt=prompt,
                model=model_name,
                config=generation_request.config,
                poll_interval=self.poll_interval_seconds,
                timeout=self.timeout_seconds,
                runtime=runtime,
            )
            logger.info(
                "Gemini video generation completed (%d bytes)",
                len(video_bytes),
            )
            return video_bytes
        except ValidationError:
            raise
        except ValueError as exc:
            logger.warning("Invalid Gemini video request: %s", exc)
            raise ValidationError(str(exc)) from exc
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive provider wrapper
            logger.error("Gemini video generation failed: %s", exc, exc_info=True)
            raise ProviderError(
                f"Gemini video generation failed: {exc}",
                provider="gemini_video",
                original_error=exc,
            ) from exc

    async def generate_from_image(
        self,
        prompt: str,
        image_url: str,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate a video from an existing image."""

        image = await source_utils.fetch_image_for_video(
            image_url, provider_name="gemini_video"
        )

        generation_request = await request_utils.build_generation_request(
            duration_seconds=kwargs.get("duration_seconds", 5),
            aspect_ratio=kwargs.get("aspect_ratio", "9:16"),
            kwargs=kwargs,
            number_of_videos=1,
            available_aspect_ratios=self.available_aspect_ratios,
            available_person_generation=self.available_person_generation,
            available_resolutions=self.available_resolutions,
            prepare_image=self._prepare_image,
            resolve_reference_type=self._resolve_reference_type,
            default_aspect_ratio="9:16",
        )

        logger.info(
            "Generating Gemini image-to-video: model=%s duration=%ss aspect_ratio=%s",
            self.model,
            generation_request.duration,
            generation_request.aspect_ratio,
        )

        try:
            video_bytes = await operations_utils.execute_generation(
                self.client,
                prompt=prompt,
                model=self._resolve_model_name(self.model),
                config=generation_request.config,
                poll_interval=self.poll_interval_seconds,
                timeout=self.timeout_seconds,
                image=image,
                runtime=runtime,
            )
            logger.info(
                "Gemini image-to-video generation completed (%d bytes)",
                len(video_bytes),
            )
            return video_bytes
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - provider failure guard
            logger.error("Gemini image-to-video failed: %s", exc, exc_info=True)
            raise ProviderError(
                f"Gemini image-to-video failed: {exc}",
                provider="gemini_video",
                original_error=exc,
            ) from exc

    async def _prepare_image(self, source: Any) -> Optional[types.Image]:
        """Wrapper around :func:`assets.prepare_image` using the provider fetcher."""

        return await assets.prepare_image(source, assets.fetch_image_bytes)

    def _resolve_reference_type(
        self, entry: Any
    ) -> Optional[types.VideoGenerationReferenceType]:
        """Resolve reference type using the configured mapping."""

        resolved = options.resolve_reference_type(entry, self.available_reference_types)
        if resolved is types.VideoGenerationReferenceType.STYLE:
            logger.warning(
                "Gemini video reference type STYLE is not supported; falling back to ASSET."
            )
            return types.VideoGenerationReferenceType.ASSET
        return resolved

    def _resolve_model_name(self, model: str | None) -> str:
        """Normalise model aliases to the canonical Gemini identifier."""

        if not model:
            return self.model

        candidate = model.strip()
        if not candidate:
            return self.model

        resolved = self._model_aliases.get(candidate.lower())
        if resolved:
            return resolved
        return candidate
