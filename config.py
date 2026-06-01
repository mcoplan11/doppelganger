import os
from dataclasses import dataclass

import truststore
from dotenv import load_dotenv

truststore.inject_into_ssl()
load_dotenv()


@dataclass(frozen=True)
class Config:
    qualtrics_token: str
    qualtrics_datacenter: str
    qualtrics_survey_id: str
    gemini_api_key: str
    gemini_model: str

    @property
    def qualtrics_base_url(self) -> str:
        return f"https://{self.qualtrics_datacenter}.qualtrics.com/API/v3"


def load_config() -> Config:
    required = {
        "QUALTRICS_API_TOKEN": os.getenv("QUALTRICS_API_TOKEN"),
        "QUALTRICS_DATACENTER": os.getenv("QUALTRICS_DATACENTER"),
        "QUALTRICS_SURVEY_ID": os.getenv("QUALTRICS_SURVEY_ID"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    }
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
        gemini_api_key=required["GEMINI_API_KEY"],
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
    )
