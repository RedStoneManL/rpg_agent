"""Global configuration values for the RPG world agent."""

import os

AGENT_CONFIG = {
    "genre": os.getenv("RPG_GENRE", "Cyberpunk/Lovecraftian"),
    "tone": os.getenv("RPG_TONE", "Dark & Gritty"),
    "final_conflict": os.getenv(
        "RPG_FINAL_CONFLICT",
        "The Awakening of the Old Ones",
    ),
    "llm": {
        "base_url": os.getenv("RPG_LLM_BASE_URL", "http://100.102.191.165:1025/v1"),
        "api_key": os.getenv("RPG_LLM_API_KEY", "xx"),
        "model": os.getenv("RPG_LLM_MODEL", "GLM-4.7-w8a8"),
        "temperature": float(os.getenv("RPG_LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.getenv("RPG_LLM_MAX_TOKENS", "48000")),
    },
    "stages": {
        "genesis": int(os.getenv("RPG_STAGE_GENESIS_TOKENS", "8000")),
        "narrator": int(os.getenv("RPG_STAGE_NARRATOR_TOKENS", "4000")),
        "map_gen": int(os.getenv("RPG_STAGE_MAP_TOKENS", "2000")),
        "cognition": int(os.getenv("RPG_STAGE_COGNITION_TOKENS", "2000")),
    },
    "storage": {
        "type": os.getenv("RPG_STORAGE_TYPE", "local"),  # "local" or "minio"
        "base_path": os.getenv("RPG_STORAGE_PATH", "./saves"),
    },
    "minio": {
        "endpoint": os.getenv("RPG_MINIO_ENDPOINT", "100.102.191.200:9000"),
        "access_key": os.getenv("RPG_MINIO_ACCESS_KEY", "minioadmin"),
        "secret_key": os.getenv("RPG_MINIO_SECRET_KEY", "minioadmin"),
        "secure": os.getenv("RPG_MINIO_SECURE", "False").lower() == "true",
        "bucket_name": os.getenv("RPG_MINIO_BUCKET", "rpg-world-data"),
    },
    "redis": {
        "host": os.getenv("RPG_REDIS_HOST", "100.102.191.198"),
        "port": int(os.getenv("RPG_REDIS_PORT", "6379")),
        "password": os.getenv("RPG_REDIS_PASSWORD"),
        "db": int(os.getenv("RPG_REDIS_DB", "0")),
        "ttl": int(os.getenv("RPG_REDIS_TTL", str(3600 * 24))),
    },
}
