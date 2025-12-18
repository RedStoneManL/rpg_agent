# 定义工具的 JSON Schema，供 Agent 的 System Prompt 使用
WORLD_GEN_TOOLS = [
    {
        "name": "generate_map_prompt",
        "description": "生成用于创建 L2 宏观地图区域数据的详细 Prompt。当需要构建世界地理结构时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "num_regions": {
                    "type": "integer", 
                    "description": "生成的区域数量 (建议 4-6)"
                },
                "geo_outlines": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "可选。指定某些区域的特征关键词 (如 ['北境冻土', '火山岛'])"
                }
            },
            "required": ["num_regions"]
        }
    },
    {
        "name": "generate_npcs_prompt",
        "description": "生成用于创建 L1 级别关键 NPC 的详细 Prompt。当需要填充世界重要人物时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "num_npcs": {
                    "type": "integer", 
                    "description": "生成的 NPC 数量"
                },
                "custom_outlines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "description": "角色定位 (e.g. 皇帝)"},
                            "traits": {"type": "string", "description": "性格或特征关键词"}
                        }
                    },
                    "description": "可选。指定 NPC 的大致设定大纲。"
                }
            },
            "required": ["num_npcs"]
        }
    }
]
