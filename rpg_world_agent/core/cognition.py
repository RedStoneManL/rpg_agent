"""Session cognition and state management backed by Redis and MinIO."""

import json
from typing import Dict, List, TypedDict

from config.settings import AGENT_CONFIG
from data.db_client import DBClient


class MessagePayload(TypedDict):
    """轻量级消息结构，用于 Redis 序列化。"""

    role: str
    content: str


class CognitionSystem:
    """Manage conversation history and player state for a session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.redis = DBClient.get_redis()
        self.ttl = AGENT_CONFIG["redis"]["ttl"]

        # Redis Key 规范
        self.history_key = f"rpg:history:{session_id}"  # 对话历史
        self.state_key = f"rpg:state:{session_id}"  # RPG 状态 (HP, Location)

    def add_message(self, role: str, content: str) -> None:
        """写入短期记忆 (对话流)。"""
        msg: MessagePayload = {"role": role, "content": content}
        self.redis.rpush(self.history_key, json.dumps(msg, ensure_ascii=False))
        self.redis.expire(self.history_key, self.ttl)

    def get_recent_history(self, limit: int = 10) -> List[MessagePayload]:
        """获取 Context Window，按需截取最近消息。"""
        raw_msgs = self.redis.lrange(self.history_key, -limit, -1)
        return [json.loads(message) for message in raw_msgs]

    def update_player_state(self, updates: Dict) -> None:
        """
        更新玩家实时状态 (比如移动了位置，扣了血)
        updates: {"hp": 90, "location_id": "loc_tavern"}
        """
        self.redis.hset(self.state_key, mapping=updates)
        self.redis.expire(self.state_key, self.ttl)

    def get_player_state(self) -> Dict:
        """获取玩家当前所有状态。"""
        return self.redis.hgetall(self.state_key)

    def archive_session(self) -> None:
        """【存档】将 Redis 中的数据打包存入 MinIO。"""
        history = self.redis.lrange(self.history_key, 0, -1)
        history_data = [json.loads(message) for message in history]
        final_state = self.get_player_state()

        archive_data = {
            "session_id": self.session_id,
            "history": history_data,
            "final_state": final_state,
        }

        object_name = f"saves/{self.session_id}.json"
        DBClient.save_json_to_minio(object_name, archive_data)
        print(f"💾 存档已上传至 MinIO: {object_name}")
