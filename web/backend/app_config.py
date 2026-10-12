from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    secret_key: str = "change-me-in-production"

    # AI Studio API key (fallback when not on Vertex). Optional so Vertex-only
    # deployments don't need it.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    # Run Gemini on Vertex AI (Google Cloud) instead of the AI Studio Developer
    # API. Vertex is what produces Cloud billing invoices + model-observability
    # dashboards. Uses GCP-standard env var names.
    gemini_use_vertex: bool = Field(default=False, validation_alias="GEMINI_USE_VERTEX")
    gemini_project: str = Field(default="", validation_alias="GOOGLE_CLOUD_PROJECT")
    gemini_location: str = Field(
        default="global", validation_alias="GOOGLE_CLOUD_LOCATION"
    )

    # OpenRouter powers the non-Gemini members of the ensemble (see ensemble.py).
    openrouter_api_key: str = ""

    resend_api_key: str = ""
    from_email: str = "Doppelganger <hello@doppelgangerlabs.com>"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # PayPal (Orders v2). Defaults to the sandbox environment — set
    # PAYPAL_BASE_URL=https://api-m.paypal.com for live payments.
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"

    frontend_url: str = "http://localhost:3000"

    # Qualtrics datacenter (e.g. "yul1") — used when building base_url for API calls
    qualtrics_datacenter: str = "yul1"

    # Token expiry for magic links (seconds)
    magic_link_expiry: int = 900  # 15 minutes

    # Session cookie lifetime (seconds)
    session_expiry: int = 60 * 60 * 24 * 30  # 30 days


settings = Settings()
