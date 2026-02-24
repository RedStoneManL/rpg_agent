"""
World Initialization Script
===========================
独立的世界初始化脚本，用于测试和独立运行世界生成功能
"""

import sys
import os
import json
import re
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rpg_world_agent.data.llm_client import get_llm_client
from rpg_world_agent.data.db_client import DBClient
from rpg_world_agent.config.settings import AGENT_CONFIG
from rpg_world_agent.core.genesis import WorldGenerator
from rpg_world_agent.core.map_engine import MapTopologyEngine


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def create_default_map() -> list:
    """创建默认地图（当 LLM 生成失败时使用）"""
    return [
        {
            "region_id": "tavern_square",
            "name": "旅店广场",
            "desc": "城镇中心的繁华广场，四周环绕着各类店铺和酒馆。石板铺就的地面上留下无数车辙和脚步，空气中弥漫着烤面包和麦酒的香气。",
            "geo_feature": "城镇广场",
            "risk_level": 1
        },
        {
            "region_id": "black_market",
            "name": "黑市",
            "desc": "隐藏在地下排水系统中的秘密市场，只有知道暗语的人才能找到。这里出售各种非法物品、魔法药水和情报。",
            "geo_feature": "地下市场",
            "risk_level": 3
        },
        {
            "region_id": "forest_entrance",
            "name": "迷雾森林入口",
            "desc": "城镇北方的森林边缘，薄雾永久不散。树木扭曲如鬼爪，风声仿佛在低语着古老的咒语。",
            "geo_feature": "森林边缘",
            "risk_level": 2
        },
        {
            "region_id": "deep_forest",
            "name": "迷雾森林深处",
            "desc": "森林最深处，迷雾浓密到几乎无法视物。这里的地形不断变化，许多冒险者在此失踪，再也没有回来。",
            "geo_feature": "茂密森林",
            "risk_level": 4
        },
        {
            "region_id": "ancient_ruins",
            "name": "古代遗迹",
            "desc": "一座被遗忘的古代遗迹，巨石上刻着看不懂的符文。夜晚时，这里会发出奇异的蓝光，吸引着不祥的生物。",
            "geo_feature": "古代遗迹",
            "risk_level": 5
        },
        {
            "region_id": "temple_district",
            "name": "神殿区",
            "desc": "城镇的神圣区域，白色的石柱和宏伟的大教堂群。这里是教会权力的中心，也是信仰者的庇护所。",
            "geo_feature": "神圣区",
            "risk_level": 1
        },
        {
            "region_id": "merchant_quarter",
            "name": "商人区",
            "desc": "繁忙的贸易区，来自各地的商队在这里交易商品。你可以在这里找到任何东西——只要你有足够的金币。",
            "geo_feature": "商业区",
            "risk_level": 2
        }
    ]


def add_default_neighbors(regions: list) -> list:
    """为默认地图添加邻居关系"""
    neighbor_map = {
        "tavern_square": ["black_market", "forest_entrance", "temple_district", "merchant_quarter"],
        "black_market": ["tavern_square"],
        "forest_entrance": ["tavern_square", "deep_forest"],
        "deep_forest": ["forest_entrance", "ancient_ruins"],
        "ancient_ruins": ["deep_forest"],
        "temple_district": ["tavern_square", "merchant_quarter"],
        "merchant_quarter": ["tavern_square", "temple_district"]
    }

    for region in regions:
        region_id = region.get("region_id")
        if region_id in neighbor_map:
            region["neighbors"] = neighbor_map[region_id]
        else:
            region["neighbors"] = []

    return regions


def initialize_world(use_llm: bool = True) -> dict:
    """
    初始化世界

    Args:
        use_llm: 是否使用 LLM 生成世界，否则使用默认地图

    Returns:
        dict: 世界数据
    """
    print_section("🌍 世界生成初始化")

    # 初始化存储连接
    print("🔗 连接存储系统...")
    try:
        redis_client = DBClient.get_redis()
        storage_adapter = DBClient.get_storage_adapter()
        print("✅ 存储连接成功\n")
    except Exception as e:
        print(f"❌ 存储连接失败: {e}\n")
        return None

    # 初始化生成器
    world_gen = WorldGenerator()

    # 配置世界参数
    print("📋 配置世界参数:")
    world_gen.update_config("genre", AGENT_CONFIG.get("genre", "Dark Fantasy"))
    world_gen.update_config("tone", AGENT_CONFIG.get("tone", "Dark & Gritty"))
    world_gen.update_config("power_level", "Epic")
    world_gen.update_config("conflict", "Random")

    print(f"   风格: {world_gen.current_config.get('genre')}")
    print(f"   基调: {world_gen.current_config.get('tone')}")
    print(f"   力量等级: Epic")
    print(f"   危机: {world_gen.current_config.get('final_conflict')}\n")

    regions = []

    if use_llm:
        # 使用 LLM 生成地图
        print_section("🏗️  使用 LLM 生成地图")

        map_prompt = world_gen.get_step_2_map_prompt(num_regions=5)

        print("正在调用 LLM 生成地图结构...")
        print("(这可能需要一些时间...)\n")

        try:
            llm_client = get_llm_client()
            response = llm_client.chat.completions.create(
                model=AGENT_CONFIG["llm"]["model"],
                messages=[{"role": "user", "content": map_prompt}],
                temperature=0.7,
                max_tokens=AGENT_CONFIG["stages"].get("map_gen", 4000)
            )
            content = response.choices[0].message.content

            # 清理和提取 JSON
            clean = re.sub(r"```json|```", "", content, flags=re.IGNORECASE).strip()
            start = clean.find("[")
            end = clean.rfind("]") + 1

            if start == -1 or end == 0:
                print("⚠️  LLM 返回的内容中未找到有效的 JSON 数组")
                print("原始内容预览:")
                print(content[:200] + "...\n")
                raise ValueError("JSON 解析失败")

            regions = json.loads(clean[start:end])
            world_gen.generated_regions = regions

            print(f"✅ 成功生成 {len(regions)} 个区域:\n")
            for i, region in enumerate(regions, 1):
                print(f"  [{i}] {region.get('name', 'Unknown')}")
                print(f"      ID: {region.get('region_id')}")
                print(f"      描述: {region.get('desc', 'N/A')[:80]}...")
                print()

        except Exception as e:
            print(f"❌ LLM 地图生成失败: {e}")
            print("将使用默认地图...\n")
            use_llm = False

    if not use_llm:
        # 使用默认地图
        print_section("📦 使用默认地图")

        regions = create_default_map()
        regions = add_default_neighbors(regions)
        world_gen.generated_regions = regions

        print(f"✅ 加载默认地图，共 {len(regions)} 个区域:\n")
        for i, region in enumerate(regions, 1):
            print(f"  [{i}] {region.get('name', 'Unknown')}")
            print(f"      ID: {region.get('region_id')}")
            print(f"      风险等级: {region.get('risk_level', 1)}")
            print(f"      邻居: {region.get('neighbors', [])}")
            print()

    # 构建地图网络
    print_section("🔨 构建地图网络")

    llm_client = get_llm_client() if use_llm else None
    success = world_gen.ingest_to_map_engine(llm_client)

    if not success:
        print("⚠️  地图网络构建可能存在问题，请检查日志")

    # 验证地图构建
    print_section("✅ 验证地图构建")

    map_engine = MapTopologyEngine()
    node_count = 0
    edge_count = 0

    for region in regions:
        region_id = region.get("region_id")
        if map_engine.node_exists(region_id):
            node_count += 1
            neighbors = map_engine.get_neighbors(region_id)
            edge_count += len(neighbors)
            print(f"  ✓ {region.get('name')} [{region_id}]")
            print(f"    连接到: {list(neighbors.keys())}")
        else:
            print(f"  ✗ {region.get('name')} [{region_id}] - 节点未找到")

    print(f"\n统计:")
    print(f"  节点数: {node_count}/{len(regions)}")
    print(f"  连接数: {edge_count}")

    # 组装最终世界数据
    world_data = world_gen.assemble_final_world(
        world_info={"name": "生成世界", "description": "LLM 生成"},
        regions=world_gen.generated_regions,
        npcs=[]
    )

    print_section("🎉 世界初始化完成")

    print(f"世界配置:")
    print(f"  共有 {len(world_gen.generated_regions)} 个区域")
    print(f"  起始地点建议: {world_gen.generated_regions[0].get('region_id') if world_gen.generated_regions else 'N/A'}")
    print(f"\n现在可以使用 main.py 开始游戏了！")

    return world_data


def list_existing_maps():
    """列出已存在的地图数据"""
    print_section("📂 已存在地图数据")

    try:
        redis_client = DBClient.get_redis()
        # 列出所有地图节点
        node_keys = redis_client.keys("rpg:map:node:*")

        if not node_keys:
            print("目前没有已保存的地图数据")
            return

        print(f"找到 {len(node_keys)} 个地图节点:\n")

        for key in sorted(node_keys):
            node_id = key.split(":", 3)[-1]
            data_str = redis_client.get(key)
            if data_str:
                try:
                    data = json.loads(data_str)
                    name = data.get("name", "Unknown")
                    node_type = data.get("type", "Unknown")
                    print(f"  • {name} [{node_id}] ({node_type})")
                except:
                    print(f"  • {node_id} (数据解析失败)")

        # 列出连接
        edge_keys = redis_client.keys("rpg:map:edges:*")
        if edge_keys:
            print(f"\n找到 {len(edge_keys)} 个连接记录")

    except Exception as e:
        print(f"❌ 读取地图数据失败: {e}")


def clear_existing_maps():
    """清除所有已存在的地图数据"""
    print_section("🗑️  清除地图数据")

    try:
        redis_client = DBClient.get_redis()

        node_keys = redis_client.keys("rpg:map:node:*")
        edge_keys = redis_client.keys("rpg:map:edges:*")
        all_keys = list(node_keys) + list(edge_keys)

        if not all_keys:
            print("没有需要清除的数据")
            return

        confirm = input(f"确定要删除 {len(all_keys)} 条记录吗？(y/N): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

        redis_client.delete(*all_keys)
        print(f"✅ 已清除 {len(all_keys)} 条记录")

    except Exception as e:
        print(f"❌ 清除失败: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("  世界初始化工具")
    print("  World Initialization Tool")
    print("=" * 60)

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "list":
            list_existing_maps()
        elif cmd == "clear":
            clear_existing_maps()
        elif cmd == "default":
            initialize_world(use_llm=False)
        else:
            print(f"未知命令: {cmd}")
            print("可用命令: list, clear, default")
    else:
        print("\n选择操作:")
        print("  [1] 使用 LLM 生成新世界")
        print("  [2] 使用默认地图")
        print("  [3] 列出已存在地图")
        print("  [4] 清除所有地图数据")
        print("  [q] 退出")

        choice = input("\n请选择 (1-4/q): ").strip().lower()

        if choice == '1':
            initialize_world(use_llm=True)
        elif choice == '2':
            initialize_world(use_llm=False)
        elif choice == '3':
            list_existing_maps()
        elif choice == '4':
            clear_existing_maps()
        elif choice == 'q':
            print("退出")
        else:
            print("无效选择")

    print()