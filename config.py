import os
from dataclasses import dataclass

import truststore
from dotenv import load_dotenv

truststore.inject_into_ssl()
load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    qualtrics_token: str
    qualtrics_datacenter: str
    qualtrics_survey_id: str
    gemini_api_key: str
    gemini_model: str
    # Vertex AI (Google Cloud) vs the Gemini Developer API (AI Studio). When
    # gemini_use_vertex is True, auth is via ADC/service account and a GCP
    # project is required instead of an API key.
    gemini_use_vertex: bool = False
    gemini_project: str = ""
    gemini_location: str = "global"

    @property
    def qualtrics_base_url(self) -> str:
        return f"https://{self.qualtrics_datacenter}.qualtrics.com/API/v3"


def load_config() -> Config:
    use_vertex = _env_bool("GEMINI_USE_VERTEX")
    required = {
        "QUALTRICS_API_TOKEN": os.getenv("QUALTRICS_API_TOKEN"),
        "QUALTRICS_DATACENTER": os.getenv("QUALTRICS_DATACENTER"),
        "QUALTRICS_SURVEY_ID": os.getenv("QUALTRICS_SURVEY_ID"),
    }
    # Gemini auth: Vertex needs a GCP project; AI Studio needs an API key.
    if use_vertex:
        required["GOOGLE_CLOUD_PROJECT"] = os.getenv("GOOGLE_CLOUD_PROJECT")
    else:
        required["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required env vars: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in values."
        )
    return Config(
        qualtrics_token=required["QUALTRICS_API_TOKEN"],
        qualtrics_datacenter=required["QUALTRICS_DATACENTER"],
        qualtrics_survey_id=required["QUALTRICS_SURVEY_ID"],
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        gemini_use_vertex=use_vertex,
        gemini_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        gemini_location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
    )
