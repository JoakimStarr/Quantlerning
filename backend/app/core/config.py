"""配置管理：读取 backend/.env。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # Quantlerning/
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"  # backend/.env


class Settings(BaseSettings):
    # extra="ignore"：.env 中未声明的变量（如 APP_ENV/LEARNING_DB_NAME）不报错
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # 应用
    app_name: str = "Quantlerning"
    app_version: str = "0.1.0"
    debug: bool = True

    # 只读数据库（quantlab 库）
    postgres_user: str = "quantlab"
    postgres_password: str = "quantlab"
    postgres_db: str = "quantlab"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # AI 追问（opencodezen，OpenAI 兼容接口；key 仅存后端）
    opencodezen_api_key: str = ""
    opencodezen_base_url: str = "https://opencode.ai/zen/v1"
    opencodezen_model: str = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
    opencodezen_max_tokens: int = 1024
    opencodezen_temperature: float = 0.4

    @property
    def ai_configured(self) -> bool:
        """AI 是否已配置可用 key。"""
        return bool(self.opencodezen_api_key.strip())

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
