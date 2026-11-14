from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = Field(default="replace-me", min_length=8)
    comfyui_url: str = "http://127.0.0.1:8188"
    workflow_path: Path = Path("examples/comfyui_workflow.example.json")
    audit_log_path: Path = Path("data/audit.jsonl")
    trigger_token: str = "character-token"
    max_revisions: int = Field(default=3, ge=0, le=5)
