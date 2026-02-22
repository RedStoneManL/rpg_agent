"""Session cognition and state management backed by Redis and MinIO."""

import json
from typing import Dict, List, Optional, TypedDict

from rpg_world_agent.config.settings import AGENT_CONFIG
from rpg_world_agent.data.db_client import DBClient
from minio.error import S3Error

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
        self.minio = DBClient.get_minio()
        self.ttl = AGENT_CONFIG["redis"]["ttl"]
        self.bucket_name = AGENT_CONFIG["minio"]["bucket_name"]

        # Redis Key 规范
        self.history_key = f"rpg:history:{session_id}"  # 对话历史
        self.state_key = f"rpg:state:{session_id}"  # RPG 状态 (HP, Location, Attributes)
        self.meta_key = f"rpg:meta:{session_id}"  # 存档元数据

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
        # 对于复杂对象（如 attributes），先序列化
        # 数值也需要转换为字符串，因为 Redis 只存储字符串
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
        # 反序列化复杂字段
        for key in ["attributes", "skills", "inventory", "quests", "story_nodes"]:
            if key in state:
                try:
                    state[key] = json.loads(state[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        # 转换数字字段为整数
        for key in ["hp", "max_hp", "sanity", "max_sanity", "level", "exp", "gold"]:
            if key in state:
                try:
                    state[key] = int(state[key])
                except (ValueError, TypeError):
                    pass
        return state

    def archive_session(self) -> str:
        """
        【存档】将 Redis 中的数据打包存入 MinIO。

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
            DBClient.save_json_to_minio(object_name, archive_data)
            print(f"💾 存档已保存: {object_name}")
            return object_name
        except Exception as e:
            raise RuntimeError(f"存档保存失败: {e}") from e

    def load_session(self) -> bool:
        """
        【读档】从 MinIO 加载存档到 Redis。

        Returns:
            bool: 加载成功返回 True，失败返回 False
        """
        object_name = f"{SAVE_PREFIX}{self.session_id}.json"

        try:
            archive_data = DBClient.load_json_from_minio(object_name)
            if not archive_data:
                print(f"❌ 存档不存在: {object_name}")
                return False

            # 恢复对话历史
            history = archive_data.get("history", [])
            self.redis.delete(self.history_key)  # 清除旧历史
            for msg in history:
                self.redis.rpush(self.history_key, json.dumps(msg, ensure_ascii=False))
            self.redis.expire(self.history_key, self.ttl)

            # 恢复玩家状态
            final_state = archive_data.get("final_state", {})
            self.redis.delete(self.state_key)  # 清除旧状态
            self.redis.hset(self.state_key, mapping=final_state)
            self.redis.expire(self.state_key, self.ttl)

            # 恢复元数据
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
        client = DBClient.get_minio()
        bucket_name = AGENT_CONFIG["minio"]["bucket_name"]
        saves = []

        try:
            objects = client.list_objects(bucket_name, prefix=SAVE_PREFIX, recursive=True)

            for obj in objects:
                object_name = obj.object_name
                # 提取 session_id (去掉完整路径和扩展名)
                session_id = object_name.replace(SAVE_PREFIX, "").replace(".json", "")

                # 尝试读取存档元数据
                archive_data = DBClient.load_json_from_minio(object_name)
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

        except S3Error as e:
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
            client = DBClient.get_minio()
            client.remove_object(self.bucket_name, object_name)
            print(f"🗑️ 存档已删除: {object_name}")
            return True
        except S3Error as e:
            print(f"❌ 删除存档失败: {e}")
            return False

    def _get_session_metadata(self) -> Dict:
        """获取当前会话的元数据。"""
        from datetime import datetime

        state = self.get_player_state()

        # 尝试从 Redis 获取已有元数据
        meta_str = self.redis.get(self.meta_key)
        if meta_str:
            try:
                metadata = json.loads(meta_str)
                # 更新时间和位置
                metadata["timestamp"] = datetime.now().isoformat()
                metadata["location"] = state.get("location", "Unknown")
                # 增加游戏时长
                metadata["playtime_minutes"] = metadata.get("playtime_minutes", 0) + 1
                return metadata
            except json.JSONDecodeError:
                pass

        # 创建新元数据
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
        """清除当前会话的 Redis 数据（不删除 MinIO 存档）。"""
        self.redis.delete(self.history_key, self.state_key, self.meta_key)
        print(f"🧹 会话数据已清除: {self.session_id}")
