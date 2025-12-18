import json
import logging
from typing import Any, Dict, List, Optional

from config.settings import AGENT_CONFIG
from core.generators import ContentGenerator
from data.db_client import DBClient

# 设置日志
logger = logging.getLogger(__name__)


class MapTopologyEngine:
    """
    AI 增强版地图引擎 (AI-Enhanced Map Engine).
    职责：
    1. 【落地】接收 Genesis 的蓝图，将其转化为图数据库节点 (Redis)。
    2. 【脑补】在建立连接时，调用 LLM 生成“路”的概念数据 (Description, Risk)。
    3. 【导航】提供查询接口，告诉 Agent 玩家周围有什么。
    """

    def __init__(self, llm_client=None):
        self.redis = DBClient.get_redis()
        self.ttl = AGENT_CONFIG["redis"]["ttl"]
        self.llm_client = llm_client  # 注入 LLM Client 用于生成路径描述

        # Redis Key 前缀规范
        self.KEY_PREFIX_NODE = "rpg:map:node:"
        self.KEY_PREFIX_EDGE = "rpg:map:edges:"

    def _get_node_key(self, node_id: str) -> str:
        return f"{self.KEY_PREFIX_NODE}{node_id}"

    def _get_edge_key(self, node_id: str) -> str:
        return f"{self.KEY_PREFIX_EDGE}{node_id}"

    # =========================================================================
    # 🏗️ 基础节点操作 (CRUD)
    # =========================================================================

    def save_node(self, node_id: str, data: Dict, node_type: str = "L3") -> bool:
        """保存/更新一个地图节点。"""
        key = self._get_node_key(node_id)
        data["node_id"] = node_id
        data["type"] = node_type
        try:
            self.redis.set(key, json.dumps(data, ensure_ascii=False))
            self.redis.expire(key, self.ttl)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("保存节点失败 %s: %s", node_id, exc)
            return False

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """读取节点信息"""
        key = self._get_node_key(node_id)
        data_str = self.redis.get(key)
        if data_str:
            return json.loads(data_str)
        return None

    def node_exists(self, node_id: str) -> bool:
        return self.redis.exists(self._get_node_key(node_id)) > 0

    def get_neighbors(self, node_id: str) -> Dict[str, str]:
        """获取所有出口"""
        return self.redis.hgetall(self._get_edge_key(node_id))

    # =========================================================================
    # 🧠 AI 驱动的连接生成 (Semantic Linking)
    # =========================================================================

    def _generate_route_concept(self, from_id: str, to_id: str, world_config: Dict[str, Any]) -> Dict[str, Any]:
        """调用 LLM 生成两个区域之间的通路设定。"""
        node_a = self.get_node(from_id)
        node_b = self.get_node(to_id)

        if not node_a or not node_b:
            return {"route_name": "迷雾小径", "description": "一片未知的迷雾区域"}

        prompt = ContentGenerator.generate_transition_prompt(
            config=world_config,
            source_node=node_a,
            target_node=node_b,
        )

        if not self.llm_client:
            print(f"⚠️ MapEngine 未配置 LLM，跳过路径生成: {from_id}->{to_id}")
            return {"route_name": "未知通路", "description": "一条漫长的旅途"}

        try:
            print(
                f"✨ [MapEngine] 正在构思 {node_a.get('name')} 到 {node_b.get('name')} 的沿途风貌..."
            )
            response = self.llm_client.chat.completions.create(
                model=AGENT_CONFIG["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )
            content = response.choices[0].message.content

            json_str = content.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1]
            if "```" in json_str:
                json_str = json_str.split("```")[0]

            return json.loads(json_str.strip())

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("路径生成失败: %s", exc)
            return {"route_name": "荒野", "description": "充满未知的荒野"}

    def connect_nodes_with_concept(self, from_id: str, to_id: str, route_data: Dict[str, Any]) -> bool:
        """建立带数据的连接 (存入 Redis Hash)。"""
        edge_key_a = self._get_edge_key(from_id)
        edge_key_b = self._get_edge_key(to_id)

        payload_a_to_b = json.dumps(
            {"target_id": to_id, "type": "Travel", "route_info": route_data},
            ensure_ascii=False,
        )

        payload_b_to_a = json.dumps(
            {"target_id": from_id, "type": "Travel", "route_info": route_data},
            ensure_ascii=False,
        )

        try:
            self.redis.hset(edge_key_a, f"Travel:{to_id}", payload_a_to_b)
            self.redis.hset(edge_key_b, f"Travel:{from_id}", payload_b_to_a)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("连接失败: %s", exc)
            return False

    # =========================================================================
    # 🌍 L2 注入逻辑
    # =========================================================================

    def ingest_l2_graph(self, generated_regions: List[Dict[str, Any]], world_config: Dict[str, Any]) -> bool:
        """
        注入 L2 地图。
        Args:
            generated_regions: 创世模块生成的区域列表
            world_config: 世界设定 (用于给 LLM 提供 Context)
        """
        print(f"🗺️ MapEngine: 开始构建世界，包含 {len(generated_regions)} 个区域...")

        for r_data in generated_regions:
            rid = r_data.get("region_id")
            if not rid:
                continue
            node_payload = {k: v for k, v in r_data.items() if k != "neighbors"}
            self.save_node(rid, node_payload, node_type="L2")

        for r_data in generated_regions:
            from_id = r_data.get("region_id")
            neighbor_ids = r_data.get("neighbors", [])

            for to_id in neighbor_ids:
                edge_key = self._get_edge_key(from_id)
                if self.redis.hexists(edge_key, f"Travel:{to_id}"):
                    continue

                route_concept = self._generate_route_concept(from_id, to_id, world_config)
                self.connect_nodes_with_concept(from_id, to_id, route_concept)

                print(
                    f"  🔗 [路网] {r_data.get('name')} <==[{route_concept.get('route_name')}]==> {to_id}"
                )

        print("✅ L2 地图构建完成。路网信息已生成。")
        return True
