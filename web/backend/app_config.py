from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    secret_key: str = "change-me-in-production"

    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash"

    resend_api_key: str = ""
    from_email: str = "Doppelganger <noreply@doppelgangerlabs.com>"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    frontend_url: str = "http://localhost:3000"

    # Qualtrics datacenter (e.g. "yul1") — used when building base_url for API calls
    qualtrics_datacenter: str = "yul1"

    # Token expiry for magic links (seconds)
    magic_link_expiry: int = 900  # 15 minutes

    # Session cookie lifetime (seconds)
    session_expiry: int = 60 * 60 * 24 * 30  # 30 days


settings = Settings()
