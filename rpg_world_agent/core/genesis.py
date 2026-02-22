"""World generation pipeline orchestrating prompts and configuration."""

import random
from typing import Any, Dict, List, Optional

from rpg_world_agent.config.seeds import CRISIS_SEEDS
from rpg_world_agent.core.generators import ContentGenerator
# 新增引用
from rpg_world_agent.core.map_engine import MapTopologyEngine


class WorldGenerator:
    """Guide multi-step world generation using prompt builders."""

    def __init__(self):
        self.required_fields = ["genre", "power_level", "tone", "conflict"]
        self.current_config: Dict[str, Any] = {}
        self.generated_world_info: Dict[str, Any] = {}
        self.generated_regions: List[Dict[str, Any]] = []
        self.generated_npcs: List[Dict[str, Any]] = []

    def update_config(self, key: str, value: str) -> bool:
        if key in self.required_fields:
            self.current_config[key] = value
            return True
        return False

    def check_missing_fields(self) -> List[str]:
        return [field for field in self.required_fields if field not in self.current_config]

    def _get_conflict_instruction(self) -> str:
        user_choice = self.current_config.get("conflict", "Random")
        if user_choice.lower() != "random":
            return user_choice

        seed = random.choice(CRISIS_SEEDS)
        salt = random.randint(10000, 99999)
        return f"基于'{seed}'概念的隐秘危机 (Seed:{salt})"

    def get_step_1_world_prompt(self) -> str:
        conflict = self._get_conflict_instruction()
        self.current_config["final_conflict"] = conflict
        return (
            "你是一个世界架构师。请为以下设定生成一个世界的基础概况：\n"
            f"- 风格: {self.current_config['genre']}\n"
            f"- 基调: {self.current_config['tone']}\n"
            f"- 危机: {conflict}\n\n"
            "输出 JSON: { \"name\": \"世界名\", \"description\": \"200字的世界观综述\", "
            "\"rules_of_magic\": \"简述魔法/力量规则\" }"
        )

    def get_step_2_map_prompt(self, num_regions: int = 5, geo_outlines: Optional[List[str]] = None) -> str:
        return ContentGenerator.generate_map_prompt(
            config=self.current_config,
            num_regions=num_regions,
            geo_outlines=geo_outlines,
        )

    def get_step_3_npc_prompt(
        self,
        generated_regions_data: List[Dict[str, Any]],
        num_npcs: int = 3,
        custom_outlines: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        return ContentGenerator.generate_npcs_prompt(
            region_data=generated_regions_data,
            num_npcs=num_npcs,
            npc_outlines=custom_outlines,
        )

    def assemble_final_world(
        self,
        world_info: Dict[str, Any],
        regions: List[Dict[str, Any]],
        npcs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "config": self.current_config,
            "world_info": world_info,
            "geo_graph_l2": regions,
            "key_npcs_l1": npcs,
        }

    # =========================================================================
    # 🏗️ 引擎对接接口
    # =========================================================================
    
    def ingest_to_map_engine(self, llm_client) -> bool:
        """
        将生成的 L2 蓝图移交给 MapEngine 进行实体化施工。
        Args:
            llm_client: 传入 LLM 客户端，以便 MapEngine 生成路径描述。
        """
        if not self.generated_regions:
            print("❌ [Genesis] 错误: 没有生成的区域数据，无法移交施工。")
            return False
            
        print("\n🏗️ [Genesis] 正在将蓝图移交给工程队 (MapEngine)...")
        # 初始化引擎并注入 LLM
        engine = MapTopologyEngine(llm_client=llm_client)
        # 传入 world_config 以便生成路途描述时有上下文
        success = engine.ingest_l2_graph(self.generated_regions, self.current_config)
        return success
