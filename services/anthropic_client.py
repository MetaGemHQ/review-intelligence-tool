import os
from functools import lru_cache

from anthropic import Anthropic


@lru_cache(maxsize=1)
def get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return Anthropic(api_key=api_key)
