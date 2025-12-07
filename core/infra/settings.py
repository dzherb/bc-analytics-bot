from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DEBUG: bool = False
    TELEGRAM_BOT_TOKEN: SecretStr

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )


class SettingsParseError(ValueError):
    pass


def provide_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as e:
        raise SettingsParseError(
            e.errors(
                include_url=False,
                include_context=False,
                include_input=False,
            ),
        ) from e
