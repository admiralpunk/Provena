from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://provena:provena_dev@localhost:5437/provena"
    bootstrap_token: str = ""
    memory_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    openai_api_key: str = ""
    extraction_model: str = "qwen2.5:1.5b"
    embedding_model: str = "nomic-embed-text"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
