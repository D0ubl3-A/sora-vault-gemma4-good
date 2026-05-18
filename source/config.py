from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"
DEFAULT_DATA_DIR = Path("/tmp/sora_vault_cloud") if os.getenv("VERCEL") else (APP_DIR / "data")
DATA_DIR = Path(os.getenv("SORA_VAULT_DATA_DIR", DEFAULT_DATA_DIR)).resolve()
DB_PATH = Path(os.getenv("SORA_VAULT_DB_PATH", DATA_DIR / "sora_vault_cloud.sqlite3")).resolve()
DEFAULT_HOST = os.getenv("SORA_VAULT_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("SORA_VAULT_PORT", "8780"))


@dataclass(frozen=True)
class PlanDefinition:
    plan_id: str
    name: str
    description: str
    monthly_price_label: str
    features: tuple[str, ...]
    device_limit: int
    root_limit: int
    stripe_price_id: str | None


PLAN_CATALOG: dict[str, PlanDefinition] = {
    "starter": PlanDefinition(
        plan_id="starter",
        name="Starter",
        description="Metadata sync for one machine with Gemma-powered search and stitch planning.",
        monthly_price_label="$19/mo",
        features=(
            "1 device",
            "metadata sync",
            "Gemma 4 search and stitch planner",
            "basic library dashboard",
        ),
        device_limit=1,
        root_limit=3,
        stripe_price_id=os.getenv("STRIPE_PRICE_STARTER") or None,
    ),
    "pro": PlanDefinition(
        plan_id="pro",
        name="Pro",
        description="Multiple devices, preview metadata, and team-ready Gemma workflows.",
        monthly_price_label="$49/mo",
        features=(
            "5 devices",
            "multi-folder sync",
            "Gemma planner with optional voice input",
            "priority search and tagging",
        ),
        device_limit=5,
        root_limit=20,
        stripe_price_id=os.getenv("STRIPE_PRICE_PRO") or None,
    ),
    "vault": PlanDefinition(
        plan_id="vault",
        name="Vault",
        description="Full backup-grade tier with room for preview uploads and team sharing.",
        monthly_price_label="$99/mo",
        features=(
            "10 devices",
            "team library sharing",
            "preview upload workflows",
            "advanced automations",
        ),
        device_limit=10,
        root_limit=100,
        stripe_price_id=os.getenv("STRIPE_PRICE_VAULT") or None,
    ),
}


class Settings:
    session_ttl_hours = int(os.getenv("SORA_VAULT_SESSION_TTL_HOURS", "720"))
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    groq_assistant_model = os.getenv("SORA_VAULT_GROQ_ASSISTANT_MODEL", "llama-3.1-8b-instant")
    groq_search_model = os.getenv("SORA_VAULT_GROQ_SEARCH_MODEL", "openai/gpt-oss-20b")
    groq_transcription_model = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
    ai_provider_default = os.getenv("SORA_VAULT_AI_PROVIDER_DEFAULT", "local_gemma")
    local_ollama_api = os.getenv("SORA_VAULT_OLLAMA_API", "http://127.0.0.1:11434/api/generate")
    local_ollama_model = os.getenv("SORA_VAULT_OLLAMA_MODEL", "gemma4:e2b")
    app_public_url = os.getenv("SORA_VAULT_PUBLIC_URL", f"http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    stripe_secret_key = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")


settings = Settings()


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
