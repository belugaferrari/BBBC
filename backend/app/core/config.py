"""Configuracao da aplicacao, lida de variaveis de ambiente / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 30
    algorithm: str = "HS256"

    database_url: str = "postgresql+psycopg://bbbc:bbbc@localhost:5432/bbbc"

    open_finance_provider: str = "none"
    pluggy_client_id: str | None = None
    pluggy_client_secret: str | None = None
    pluggy_webhook_secret: str | None = None
    belvo_secret_id: str | None = None
    belvo_secret_password: str | None = None
    belvo_env: str = "sandbox"
    belvo_webhook_secret: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def assert_production_ready(self) -> None:
        """Falha no boot em vez de rodar em producao com o segredo de exemplo.

        Um SECRET_KEY conhecido permite forjar qualquer token de acesso.
        """
        if not self.is_production:
            return
        problems: list[str] = []
        if self.secret_key in {"dev-secret-change-me", "", None} or len(self.secret_key) < 32:
            problems.append("SECRET_KEY precisa ser um segredo proprio com 32+ caracteres")
        if "localhost" in self.database_url:
            problems.append("DATABASE_URL ainda aponta para localhost")
        if problems:
            raise RuntimeError("configuracao invalida para producao: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
