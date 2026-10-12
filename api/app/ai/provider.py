from functools import cache
from typing import Annotated

from fastapi import Depends
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.config import settings


@cache
def _gemini(api_key: str, model_name: str) -> GoogleModel:
    # Built once per key/model and reused, so requests share one HTTP client.
    return GoogleModel(model_name, provider=GoogleProvider(api_key=api_key))


def get_ai_model() -> Model | None:
    """The model the AI features run on, or None when no key is configured.

    The key comes from the API's settings (api/.env), is passed straight to the
    provider and never appears in a response. Tests override this dependency
    with Pydantic AI's `TestModel`/`FunctionModel`.
    """
    if not settings.GOOGLE_API_KEY:
        return None
    return _gemini(settings.GOOGLE_API_KEY, settings.AI_MODEL)


AIModel = Annotated[Model | None, Depends(get_ai_model)]
