"""Prompt builders for NPC, map, and transition generation."""

import json
from typing import Any, Dict, List, Optional

from config.rules import VALID_SKILLS, VALID_TAG_CATEGORIES

NPC_L1_PROMPT_TEMPLATE = """
你是一个严谨的 RPG 数据策划。请基于以下规则和约束，生成 NPC 数据。

【元数据约束 (Metadata Constraints)】
请严格从以下列表中选择 Tag 和 Skill，**绝对不要**创造列表中不存在的技能或标签：
- 合法技能库 (Skills): {valid_skills_str}
- 合法标签库 (Tags): {valid_tags_str}

【生成任务配置】
- 世界区域列表: 
{region_list_str}
- 任务目标: 生成 {num_npcs} 名 L1 级别 NPC。
{npc_outlines_instruction}

【输出数据结构】
请生成一个 JSON 列表。每个人物的 `layers` 字段必须包含洋葱结构信息。
在定义 `access_condition` (访问条件) 时，必须使用上述合法库中的词条。

JSON Schema 示例:
[
  {{
    "npc_id": "string",
    "name": "string",
    "home_region_id": "string (必须来自区域列表)",
    "layers": {{
      "public": {{ ... }},
      "social": {{
        "desc": "...",
        "access_req": {{ 
           "logic": "OR", 
           "tags": ["noble"],  <-- 必须在合法标签库中
           "skills": ["insight"] <-- 必须在合法技能库中
        }}
      }}
    }}
  }}
]
"""

MAP_L2_PROMPT_TEMPLATE = """
你是一个地图架构师。
当前设定: {world_setting_summary}

任务目标:
生成 {num_regions} 个主要区域 (Regions)。
{geo_outlines_instruction}

请构建区域间的 neighbors 拓扑关系，并输出 JSON。
"""

# =============================================================================
# 🛣️ 过渡区域生成工具 (Transition Tool) - 新增！
# =============================================================================

TRANSITION_PROMPT_TEMPLATE = """
你是一个负责设计关卡连接的地图设计师。
世界设定: {world_setting}

任务：设计连接以下两个区域的【过渡地带 (Transition Zone)】。

【起点】: {source_name} ({source_geo})
【终点】: {target_name} ({target_geo})

请设想这两个区域之间的一条主要通路。
要求：
1. 给这条路起个名字 (e.g. 悲鸣山道, 黄金海道)。
2. 描述沿途的地理风貌和潜在危险 (Rumors)。
3. 设定旅行难度 (1-5)。

请输出纯 JSON 格式 (不要包含 Markdown 标记):
{
    "route_name": "通路名称",
    "geo_type": "地貌类型 (e.g. 森林, 沙漠, 海洋)",
    "description": "一段关于这条路的描述，用于向导向玩家介绍",
    "risk_level": 3,
    "rumors": ["传闻1", "传闻2"]
}
"""


class ContentGenerator:
    """Dynamic prompt builders for RPG content generation."""

    @staticmethod
    def _format_list(items: List[str]) -> str:
        return ", ".join([f'"{item}"' for item in items])

    @classmethod
    def generate_npcs_prompt(
        cls,
        region_data: List[Dict[str, Any]],
        num_npcs: int = 3,
        npc_outlines: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build the NPC generation prompt string."""
        valid_skills_str = cls._format_list(VALID_SKILLS)
        valid_tags_str = cls._format_list(VALID_TAG_CATEGORIES)
        regions_summary = "\n".join(
            [f"- ID: {region.get('region_id')}, Name: {region.get('name')}" for region in region_data]
        )

        if npc_outlines:
            instruction_lines = ["- 指定大纲要求:"]
            for index, outline in enumerate(npc_outlines):
                instruction_lines.append(f"  NPC_{index + 1}: {json.dumps(outline, ensure_ascii=False)}")
            if len(npc_outlines) < num_npcs:
                instruction_lines.append(f"  (剩余 {num_npcs - len(npc_outlines)} 名 NPC 请自由发挥)")
            npc_outlines_instruction = "\n".join(instruction_lines)
        else:
            npc_outlines_instruction = "- 无具体大纲，请自由发挥，但需符合世界观。"

        return NPC_L1_PROMPT_TEMPLATE.format(
            valid_skills_str=valid_skills_str,
            valid_tags_str=valid_tags_str,
            region_list_str=regions_summary,
            num_npcs=num_npcs,
            npc_outlines_instruction=npc_outlines_instruction,
        )

    @classmethod
    def generate_map_prompt(
        cls,
        config: Dict[str, Any],
        num_regions: int = 5,
        geo_outlines: Optional[List[str]] = None,
    ) -> str:
        """Build the map generation prompt string."""
        outlines_str = ""
        if geo_outlines:
            outlines_str = "指定区域要求: " + ", ".join(geo_outlines)

        world_summary = f"风格:{config.get('genre')}, 危机:{config.get('final_conflict')}"
        return MAP_L2_PROMPT_TEMPLATE.format(
            world_setting_summary=world_summary,
            num_regions=num_regions,
            geo_outlines_instruction=outlines_str,
        )

    @classmethod
    def generate_transition_prompt(
        cls,
        config: Dict[str, Any],
        source_node: Dict[str, Any],
        target_node: Dict[str, Any],
    ) -> str:
        """Generate the prompt for creating a transition zone between two regions."""
        world_summary = f"风格:{config.get('genre')}, 危机:{config.get('final_conflict')}"

        return TRANSITION_PROMPT_TEMPLATE.format(
            world_setting=world_summary,
            source_name=source_node.get("name"),
            source_geo=source_node.get("geo_feature", "未知"),
            target_name=target_node.get("name"),
            target_geo=target_node.get("geo_feature", "未知"),
        )
