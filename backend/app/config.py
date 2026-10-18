from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_url : str
    mongo_db : str = "atajo_db"
    base_url : str = "http://localhost:8000"
    # Comma-separated list of valid API keys. Empty = every protected call is rejected.
    api_keys : str = ""
    clicks_retention_days : int = 90

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]


settings = Settings()
