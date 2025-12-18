import json
import logging
import re
from typing import Dict, List, Optional

from config.settings import AGENT_CONFIG
from core.generators import ContentGenerator
from data.db_client import DBClient

# 设置日志
logger = logging.getLogger(__name__)


class MapTopologyEngine:
    """
    AI 增强版地图引擎 (AI-Enhanced Map Engine).
    """

    def __init__(self, llm_client=None):
        self.redis = DBClient.get_redis()
        self.ttl = AGENT_CONFIG["redis"]["ttl"]
        self.llm_client = llm_client

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
        key = self._get_node_key(node_id)
        data["node_id"] = node_id
        data["type"] = node_type
        try:
            self.redis.set(key, json.dumps(data, ensure_ascii=False))
            self.redis.expire(key, self.ttl)
            return True
        except Exception as e:
            logger.error(f"保存节点失败 {node_id}: {e}")
            return False

    def get_node(self, node_id: str) -> Optional[Dict]:
        key = self._get_node_key(node_id)
        data_str = self.redis.get(key)
        if data_str:
            return json.loads(data_str)
        return None

    def node_exists(self, node_id: str) -> bool:
        return self.redis.exists(self._get_node_key(node_id)) > 0

    def get_neighbors(self, node_id: str) -> Dict[str, str]:
        return self.redis.hgetall(self._get_edge_key(node_id))

    # =========================================================================
    # 🧠 AI 驱动的连接生成 (Semantic Linking)
    # =========================================================================

    def _generate_route_concept(self, from_id: str, to_id: str, world_config: Dict) -> Dict:
        """调用 LLM 生成两个区域之间的通路设定。"""
        node_a = self.get_node(from_id)
        node_b = self.get_node(to_id)

        if not node_a or not node_b:
            return {"route_name": "迷雾小径", "description": "一片未知的迷雾区域"}

        prompt = ContentGenerator.generate_transition_prompt(
            config=world_config, source_node=node_a, target_node=node_b
        )

        if not self.llm_client:
            print(f"⚠️ MapEngine 未配置 LLM，跳过路径生成: {from_id}->{to_id}")
            return {"route_name": "未知通路", "description": "无 LLM 支持"}

        try:
            print(f"✨ [MapEngine] 请求 AI 构思: {node_a.get('name')} -> {node_b.get('name')}")
            
            # 【解锁】直接使用全局配置的最大 Token 数
            max_tokens_limit = AGENT_CONFIG["llm"].get("max_tokens", 8000)
            
            response = self.llm_client.chat.completions.create(
                model=AGENT_CONFIG["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens_limit,  # 爽快地用！
            )
            content = response.choices[0].message.content

            # --- 鲁棒的清洗逻辑 ---
            
            # 1. (可选) 去除 <think> 标签 (Qwen-Reasoning 可能会有)
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

            # 2. 寻找 JSON 的核心部分
            start_idx = content.find('{')
            end_idx = content.rfind('}')

            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx : end_idx + 1]
                return json.loads(json_str)
            else:
                print(f"⚠️ [JSON Parse Warning] 未找到 JSON 结构，原始内容:\n{content}")
                raise ValueError("无法从回复中提取 JSON")

        except Exception as e:
            print(f"\n❌ [MapEngine Error] 解析失败: {e}")
            if "content" in locals():
                print(f"--- LLM 返回的原始内容 ---\n{content}\n------------------------")
            
            return {
                "route_name": "ERROR_FALLBACK",
                "geo_type": "Bug之地",
                "description": f"生成失败。异常: {str(e)[:50]}...",
                "risk_level": 99,
                "rumors": ["程序员正在修 Bug"]
            }

    def connect_nodes_with_concept(
        self, from_id: str, to_id: str, route_data: Dict
    ) -> bool:
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
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False

    # =========================================================================
    # 🌍 L2 注入逻辑
    # =========================================================================

    def ingest_l2_graph(self, generated_regions: List[Dict], world_config: Dict) -> bool:
        print(f"🗺️ MapEngine: 开始构建世界，包含 {len(generated_regions)} 个区域...")

        # 1. 实体化节点
        for r_data in generated_regions:
            rid = r_data.get("region_id")
            if not rid:
                continue
            node_payload = {k: v for k, v in r_data.items() if k != "neighbors"}
            self.save_node(rid, node_payload, node_type="L2")

        # 2. 建立带概念的连接
        for r_data in generated_regions:
            from_id = r_data.get("region_id")
            neighbor_ids = r_data.get("neighbors", [])

            for to_id in neighbor_ids:
                # 检查是否已存在连接
                edge_key = self._get_edge_key(from_id)
                if self.redis.hexists(edge_key, f"Travel:{to_id}"):
                    continue

                # === 此处调用 LLM 生成路途信息 ===
                route_concept = self._generate_route_concept(from_id, to_id, world_config)

                # 存入数据库
                self.connect_nodes_with_concept(from_id, to_id, route_concept)

                print(
                    f"  🔗 [路网] {r_data.get('name')} <==[{route_concept.get('route_name')}]<==> {to_id}"
                )

        print("✅ L2 地图构建完成。路网信息已生成。")
        return True
