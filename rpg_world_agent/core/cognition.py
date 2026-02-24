"""Session cognition and state management backed by Redis and storage adapters."""

import json
from typing import Dict, List, Optional, TypedDict

from rpg_world_agent.config.settings import AGENT_CONFIG
from rpg_world_agent.data.db_client import DBClient

SAVE_PREFIX = "saves/"


class MessagePayload(TypedDict):
    """轻量级消息结构，用于 Redis 序列化。"""

    role: str
    content: str


class SaveMetadata(TypedDict):
    """存档元数据结构。"""

    session_id: str
    timestamp: str
    playtime_minutes: int
    location: str
    hp: int
    sanity: int


class CognitionSystem:
    """Manage conversation history and player state for a session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.redis = DBClient.get_redis()
        self.storage = DBClient.get_storage_adapter()
        self.ttl = AGENT_CONFIG["redis"]["ttl"]
        self.bucket_name = AGENT_CONFIG["minio"]["bucket_name"]
        self.storage_type = AGENT_CONFIG.get("storage", {}).get("type", "local")

        # Redis Key 规范
        self.history_key = f"rpg:history:{session_id}"
        self.state_key = f"rpg:state:{session_id}"
        self.meta_key = f"rpg:meta:{session_id}"

    def add_message(self, role: str, content: str) -> None:
        """写入短期记忆 (对话流)。"""
        msg: MessagePayload = {"role": role, "content": content}
        self.redis.rpush(self.history_key, json.dumps(msg, ensure_ascii=False))
        self.redis.expire(self.history_key, self.ttl)

    def get_recent_history(self, limit: int = 10) -> List[MessagePayload]:
        """获取 Context Window，按需截取最近消息。"""
        raw_msgs = self.redis.lrange(self.history_key, -limit, -1)
        return [json.loads(message) for message in raw_msgs]

    def get_all_history(self) -> List[MessagePayload]:
        """获取完整的对话历史。"""
        raw_msgs = self.redis.lrange(self.history_key, 0, -1)
        return [json.loads(message) for message in raw_msgs]

    def update_player_state(self, updates: Dict) -> None:
        """
        更新玩家实时状态 (比如移动了位置，扣了血)
        updates: {"hp": 90, "location": "loc_tavern", "attributes": {...}}
        """
        for key, value in updates.items():
            if isinstance(value, (dict, list)):
                updates[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, (int, float, bool)):
                updates[key] = str(value)
            else:
                updates[key] = value
        self.redis.hset(self.state_key, mapping=updates)
        self.redis.expire(self.state_key, self.ttl)

    def get_player_state(self) -> Dict:
        """获取玩家当前所有状态。"""
        state = self.redis.hgetall(self.state_key)
        for key in ["attributes", "skills", "inventory", "quests", "story_nodes"]:
            if key in state:
                try:
                    state[key] = json.loads(state[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        for key in ["hp", "max_hp", "sanity", "max_sanity", "level", "exp", "gold"]:
            if key in state:
                try:
                    state[key] = int(state[key])
                except (ValueError, TypeError):
                    pass
        return state

    def archive_session(self) -> str:
        """
        【存档】将 Redis 中的数据打包存入存储。

        Returns:
            str: 存档对象名称 (如 "saves/session_001.json")

        Raises:
            RuntimeError: 如果存档失败
        """
        history_data = self.get_all_history()
        final_state = self.get_player_state()
        metadata = self._get_session_metadata()

        archive_data = {
            "session_id": self.session_id,
            "metadata": metadata,
            "history": history_data,
            "final_state": final_state,
        }

        object_name = f"{SAVE_PREFIX}{self.session_id}.json"
        try:
            DBClient.save_json(object_name, archive_data)
            print(f"💾 存档已保存: {object_name}")
            return object_name
        except Exception as e:
            raise RuntimeError(f"存档保存失败: {e}") from e

    def load_session(self) -> bool:
        """
        【读档】从存储加载存档到 Redis。

        Returns:
            bool: 加载成功返回 True，失败返回 False
        """
        object_name = f"{SAVE_PREFIX}{self.session_id}.json"

        try:
            archive_data = DBClient.load_json(object_name)
            if not archive_data:
                print(f"❌ 存档不存在: {object_name}")
                return False

            history = archive_data.get("history", [])
            self.redis.delete(self.history_key)
            for msg in history:
                self.redis.rpush(self.history_key, json.dumps(msg, ensure_ascii=False))
            self.redis.expire(self.history_key, self.ttl)

            final_state = archive_data.get("final_state", {})
            self.redis.delete(self.state_key)
            self.redis.hset(self.state_key, mapping=final_state)
            self.redis.expire(self.state_key, self.ttl)

            metadata = archive_data.get("metadata", {})
            meta_str = json.dumps(metadata, ensure_ascii=False)
            self.redis.set(self.meta_key, meta_str)
            self.redis.expire(self.meta_key, self.ttl)

            print(f"📂 存档已加载: {object_name}")
            print(f"   时间: {metadata.get('timestamp', 'Unknown')}")
            print(f"   位置: {metadata.get('location', 'Unknown')}")
            print(f"   状态: HP {final_state.get('hp', 'N/A')} | SAN {final_state.get('sanity', 'N/A')}")
            return True

        except Exception as e:
            print(f"❌ 存档加载失败: {e}")
            return False

    @staticmethod
    def list_saves() -> List[SaveMetadata]:
        """
        【列出存档】获取所有可用存档的元数据列表。

        Returns:
            List[SaveMetadata]: 存档元数据列表
        """
        storage = DBClient.get_storage_adapter()
        saves = []

        try:
            objects = storage.list_objects(prefix=SAVE_PREFIX)

            for object_name in objects:
                session_id = object_name.replace(SAVE_PREFIX, "").replace(".json", "")

                archive_data = DBClient.load_json(object_name)
                if archive_data:
                    metadata = archive_data.get("metadata", {})
                    final_state = archive_data.get("final_state", {})

                    saves.append(SaveMetadata(
                        session_id=metadata.get("session_id", session_id),
                        timestamp=metadata.get("timestamp", "Unknown"),
                        playtime_minutes=metadata.get("playtime_minutes", 0),
                        location=metadata.get("location", "Unknown"),
                        hp=final_state.get("hp", "N/A"),
                        sanity=final_state.get("sanity", "N/A"),
                    ))

        except Exception as e:
            print(f"❌ 列出存档失败: {e}")

        return saves

    def delete_save(self) -> bool:
        """
        【删除存档】删除当前会话的存档。

        Returns:
            bool: 删除成功返回 True，失败返回 False
        """
        object_name = f"{SAVE_PREFIX}{self.session_id}.json"

        try:
            DBClient.delete_json(object_name)
            print(f"🗑️ 存档已删除: {object_name}")
            return True
        except Exception as e:
            print(f"❌ 删除存档失败: {e}")
            return False

    def _get_session_metadata(self) -> Dict:
        """获取当前会话的元数据。"""
        from datetime import datetime

        state = self.get_player_state()

        meta_str = self.redis.get(self.meta_key)
        if meta_str:
            try:
                metadata = json.loads(meta_str)
                metadata["timestamp"] = datetime.now().isoformat()
                metadata["location"] = state.get("location", "Unknown")
                metadata["playtime_minutes"] = metadata.get("playtime_minutes", 0) + 1
                return metadata
            except json.JSONDecodeError:
                pass

        return {
            "session_id": self.session_id,
            "created_at": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "playtime_minutes": 1,
            "location": state.get("location", "Start"),
            "hp": state.get("hp", 100),
            "sanity": state.get("sanity", 100),
        }

    def clear_session(self) -> None:
        """清除当前会话的 Redis 数据（不删除存档）。"""
        self.redis.delete(self.history_key, self.state_key, self.meta_key)
        print(f"🧹 会话数据已清除: {self.session_id}")
