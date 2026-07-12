import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"


def get_fireworks_client() -> OpenAI:
    """
    Fireworks exposes an OpenAI-compatible endpoint, so the standard openai
    client works unmodified -- just point base_url at Fireworks and use a
    Fireworks API key.
    """
    api_key = os.environ.get("FIREWORKS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FIREWORKS_API_KEY not set. Copy .env.example to .env and fill it in."
        )
    return OpenAI(api_key=api_key, base_url=FIREWORKS_BASE_URL)
