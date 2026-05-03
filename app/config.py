from functools import lru_cache

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    database_url: str = Field(alias='DATABASE_URL')
    secret_key: str = Field(alias='SECRET_KEY')
    session_cookie_name: str = Field(default='sistema_b_session', alias='SESSION_COOKIE_NAME')

    keycloak_url: AnyHttpUrl = Field(alias='KEYCLOAK_URL')
    keycloak_realm: str = Field(alias='KEYCLOAK_REALM')
    keycloak_client_id: str = Field(alias='KEYCLOAK_CLIENT_ID')
    keycloak_client_secret: str = Field(alias='KEYCLOAK_CLIENT_SECRET')
    keycloak_redirect_uri: str = Field(alias='KEYCLOAK_REDIRECT_URI')

    vault_url: AnyHttpUrl = Field(alias='VAULT_URL')
    vault_token: str = Field(alias='VAULT_TOKEN')
    vault_transit_key: str = Field(alias='VAULT_TRANSIT_KEY')

    sistema_a_api_key: str = Field(alias='SISTEMA_A_API_KEY')

    app_url: AnyHttpUrl = Field(alias='APP_URL')
    app_name: str = Field(default='Apuestas EC', alias='APP_NAME')
    app_description: str = Field(default='Comparador de cuotas LigaPro y Tri', alias='APP_DESCRIPTION')

    environment: str = Field(default='development', alias='ENVIRONMENT')
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

    admin_emails: list[str] = Field(default_factory=list, alias='ADMIN_EMAILS')

    scrapers_initial_run_delay_seconds: int = Field(default=30, alias='SCRAPERS_INITIAL_RUN_DELAY_SECONDS')
    scrapers_interval_hours: int = Field(default=6, alias='SCRAPERS_INTERVAL_HOURS')
    scrapers_timeout_seconds: int = Field(default=60, alias='SCRAPERS_TIMEOUT_SECONDS')

    @field_validator('admin_emails', mode='before')
    @classmethod
    def _split_admin_emails(cls, value: object) -> list[str]:
        if value is None or value == '':
            return []
        if isinstance(value, list):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        return [item.strip().lower() for item in str(value).split(',') if item.strip()]

    @property
    def keycloak_issuer(self) -> str:
        return f'{str(self.keycloak_url).rstrip("/")}/realms/{self.keycloak_realm}'

    @property
    def oidc_discovery_url(self) -> str:
        return f'{self.keycloak_issuer}/.well-known/openid-configuration'

    def is_admin_email(self, email: str | None) -> bool:
        if not email:
            return False
        return email.strip().lower() in self.admin_emails


@lru_cache
def get_settings() -> Settings:
    return Settings()
