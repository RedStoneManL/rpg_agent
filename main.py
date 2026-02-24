"""
RPG Game Engine - Main Entry Point
=====================================
LLM驱动的TRPG游戏引擎主入口
"""

import sys
import os
import json
import re
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rpg_world_agent.data.llm_client import get_llm_client
from rpg_world_agent.data.db_client import DBClient
from rpg_world_agent.config.settings import AGENT_CONFIG
from rpg_world_agent.core.runtime import RuntimeEngine
from rpg_world_agent.core.cognition import CognitionSystem
from rpg_world_agent.core.player_character import PlayerCharacter, create_character
from rpg_world_agent.core.genesis import WorldGenerator
from rpg_world_agent.agents.world_builder import WorldBuilderAgent


def print_banner():
    """打印游戏启动横幅"""
    banner = """
    ╔════════════════════════════════════════════════════════════╗
    ║                    🎮 LLM-Driven TRPG Engine                    ║
    ║                     大语言模型驱动的TRPG游戏引擎                     ║
    ╚════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_player_status(engine: RuntimeEngine) -> None:
    """打印玩家状态"""
    state = engine.cognition.get_player_state()
    current_loc = state.get("location", "Unknown")

    loc_data = engine.map_engine.get_node(current_loc)
    loc_name = loc_data.get("name", current_loc) if loc_data else current_loc

    print(f"\n{'='*60}")
    print(f"📍 当前位置: {loc_name}")
    print(f"❤️  HP: {state.get('hp', 100)}/100  🧠 SAN: {state.get('sanity', 100)}/100")
    print(f"🏷️  标签: {', '.join(state.get('tags', []))}")
    print(f"{'='*60}\n")


def print_help() -> None:
    """打印帮助信息"""
    help_text = """
    📖 游戏指令帮助:
    ══════════════════════════════════════════════════════════

    🔍 探索类:
       /look              - 查看当前环境
       /move <地点ID>      - 移动到指定地点
       /exits             - 查看所有可前往的地点

    💬 交互类:
       自然语言输入      - 描述你的行动、对话或观察
                          例如: "我想找商店"、"攻击守卫"、"和NPC对话"

    🎮 游戏管理:
       /status            - 查看角色状态
       /map               - 查看已探索地图
       /save              - 保存游戏进度
       /load              - 加载存档
       /help              - 显示此帮助
       /quit 或 /exit     - 退出游戏

    🔧 调试/管理:
       /events            - 查看游戏事件记录
       /world             - 查看世界状态
       /plugins           - 查看已加载插件

    ══════════════════════════════════════════════════════════
    """
    print(help_text)


def list_exits(engine: RuntimeEngine) -> None:
    """列出所有可前往的地点"""
    state = engine.cognition.get_player_state()
    current_loc = state.get("location")

    if not current_loc:
        print("❌ 当前位置无效")
        return

    neighbors = engine.map_engine.get_neighbors(current_loc)

    if not neighbors:
        print("🚫 当前地点没有通路")
        return

    print(f"\n🚪 可前往的地点:")
    print("─" * 40)
    for key, payload_str in neighbors.items():
        try:
            payload = json.loads(payload_str)
            target_id = payload.get("target_id")
            route_info = payload.get("route_info", {})
            route_name = route_info.get("route_name", key)
            route_desc = route_info.get("description", "")

            # 获取目标地点信息
            target_data = engine.map_engine.get_node(target_id)
            target_name = target_data.get("name", target_id) if target_data else target_id

            print(f"  {target_id:30s} - {target_name}")
            print(f"  {' ':34s} ↳ {route_name}: {route_desc[:50]}...")
            print()
        except Exception:
            print(f"  {key.split(':')[1]}")
    print()


def show_map_summary(engine: RuntimeEngine) -> None:
    """显示已探索的地图概览"""
    state = engine.cognition.get_player_state()
    current_loc = state.get("location", "Unknown")

    print(f"\n🗺️  地图概览 (当前位置: {current_loc}):")
    print("─" * 50)

    # 简化显示：列出所有从当前地点可达的地点
    neighbors = engine.map_engine.get_neighbors(current_loc)
    if neighbors:
        for key in neighbors.keys():
            target_id = key.split(":")[1]
            target_data = engine.map_engine.get_node(target_id)
            if target_data:
                name = target_data.get("name", target_id)
                print(f"  • {name} [{target_id}]")

    print("\n[显示为简化版地图，完整地图功能开发中...]\n")


def save_game(engine: RuntimeEngine) -> bool:
    """保存游戏"""
    try:
        object_name = engine.cognition.archive_session()
        print(f"✅ 游戏已保存！存档位置: {object_name}")
        return True
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return False


def load_game(engine: RuntimeEngine) -> bool:
    """加载游戏"""
    session_id = engine.session_id
    try:
        success = engine.cognition.load_session()
        if success:
            print(f"✅ 游戏已加载！")
            print_player_status(engine)
        return success
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return False


def show_character_status(engine: RuntimeEngine) -> None:
    """显示详细角色状态"""
    state = engine.cognition.get_player_state()

    print(f"\n🎭 角色状态详情:")
    print("=" * 50)

    # 基础状态
    print(f"\n📊 基础属性:")
    print(f"   ❤️  生命值: {state.get('hp', 100)}/100")
    print(f"   🧠 理智值: {state.get('sanity', 100)}/100")

    # 位置和标签
    print(f"\n📍 当前状况:")
    current_loc = state.get("location", "Unknown")
    loc_data = engine.map_engine.get_node(current_loc)
    loc_name = loc_data.get("name", current_loc) if loc_data else current_loc
    print(f"   位置: {loc_name} ({current_loc})")
    print(f"   标签: {', '.join(state.get('tags', []))}")

    # 技能
    skills = state.get('skills', {})
    if skills:
        print(f"\n🎯 技能熟练度:")
        for skill, level in skills.items():
            print(f"   {skill:20s}: {'★' * level}{'☆' * (5 - level)}")

    # 最近历史
    print(f"\n📜 最近行动:")
    history = engine.cognition.get_recent_history(limit=3)
    for msg in history[-6:]:
        role = msg.get("role", "")
        content = msg.get("content", "").strip()
        if content and not content.startswith("System"):
            prefix = "👤 玩家" if role == "user" else "🎮 DM  "
            print(f"   {prefix}: {content[:60]}...")

    print("=" * 50 + "\n")


def initialize_new_world() -> Dict:
    """初始化新世界"""
    print("\n🌍 正在初始化新世界...")

    # 初始化生成器
    world_gen = WorldGenerator()

    # 配置世界参数
    print("\n📋 配置世界参数:")
    world_gen.update_config("genre", AGENT_CONFIG.get("genre", "Dark Fantasy"))
    world_gen.update_config("tone", AGENT_CONFIG.get("tone", "Dark & Gritty"))
    world_gen.update_config("power_level", "Epic")
    world_gen.update_config("conflict", "Random")  # 随机选择危机

    print(f"   风格: {world_gen.current_config.get('genre')}")
    print(f"   基调: {world_gen.current_config.get('tone')}")
    print(f"   危机: {world_gen.current_config.get('final_conflict')}")

    # 获取 LLM 客户端
    llm_client = get_llm_client()

    print("\n🏗️  生成世界地理结构...")
    map_prompt = world_gen.get_step_2_map_prompt(num_regions=5)

    try:
        response = llm_client.chat.completions.create(
            model=AGENT_CONFIG["llm"]["model"],
            messages=[{"role": "user", "content": map_prompt}],
            temperature=0.7,
            max_tokens=AGENT_CONFIG["stages"].get("map_gen", 4000)
        )
        content = response.choices[0].message.content

        # 提取 JSON
        clean = re.sub(r"```json|```", "", content, flags=re.IGNORECASE).strip()
        start = clean.find("[")
        end = clean.rfind("]") + 1

        if start == -1 or end == 0:
            raise ValueError("无法解析地图 JSON")

        regions = json.loads(clean[start:end])
        world_gen.generated_regions = regions

        print(f"   ✅ 生成了 {len(regions)} 个区域:")
        for region in regions:
            print(f"      • {region.get('name', 'Unknown')} [{region.get('region_id')}]")

    except Exception as e:
        print(f"   ⚠️  地图生成失败: {e}")
        print("   使用默认地图...")
        regions = [
            {
                "region_id": "tavern_square",
                "name": "酒馆广场",
                "desc": "城镇中心的繁华广场，周围环绕着各种商店和酒馆",
                "geo_feature": "城镇广场",
                "neighbors": ["black_market", "forest_entrance"]
            },
            {
                "region_id": "black_market",
                "name": "黑市",
                "desc": "隐藏在阴影中的地下市场，出售各种非法物品和情报",
                "geo_feature": "地下市场",
                "neighbors": ["tavern_square"]
            },
            {
                "region_id": "forest_entrance",
                "name": "迷雾森林入口",
                "desc": "森林边缘，薄雾弥漫，隐约可见诡异的树影",
                "geo_feature": "森林边缘",
                "neighbors": ["tavern_square", "deep_forest"]
            },
            {
                "region_id": "deep_forest",
                "name": "迷雾森林深处",
                "desc": "森林深处，完全被迷雾笼罩，充满了未知的危险",
                "geo_feature": "茂密森林",
                "neighbors": ["forest_entrance", "ancient_ruins"]
            },
            {
                "region_id": "ancient_ruins",
                "name": "古代遗迹",
                "desc": "一座古老的遗迹残骸，散发着神秘的气息",
                "geo_feature": "古代遗迹",
                "neighbors": ["deep_forest"]
            }
        ]
        world_gen.generated_regions = regions
        for region in regions:
            print(f"      • {region.get('name', 'Unknown')} [{region.get('region_id')}]")

    # 将地图注入引擎
    print("\n🔨 构建世界地图网络...")
    success = world_gen.ingest_to_map_engine(llm_client)

    if success:
        print("✅ 世界初始化完成！")
    else:
        print("⚠️  地图构建出现问题，但游戏可以继续")

    return world_gen.assemble_final_world(
        world_info={},
        regions=world_gen.generated_regions,
        npcs=[]
    )


def main():
    """主函数"""
    print_banner()

    # 检查存储连接
    print("🔗 检查存储连接...")
    try:
        DBClient.get_redis()
        DBClient.get_storage_adapter()
        print("✅ 存储系统连接正常\n")
    except Exception as e:
        print(f"❌ 存储系统连接失败: {e}")
        print("请检查配置文件 settings.py 中的服务地址\n")
        return

    # 询问是否加载已有游戏
    print("是否加载已有存档？")
    print("  [1] - 加载存档")
    print("  [2] - 新建游戏")
    choice = input("请选择 (1-2): ").strip()

    session_id = None
    start_location = "tavern_square"  # 默认起始位置

    if choice == "1":
        # 列出可用存档
        saves = CognitionSystem.list_saves()
        if not saves:
            print("❌ 没有找到任何存档")
            print("将创建新游戏...\n")
        else:
            print(f"\n📂 可用存档 ({len(saves)} 个):")
            for i, save in enumerate(saves, 1):
                print(f"  [{i}] {save['session_id']}")
                print(f"      时间: {save['timestamp']}")
                print(f"      位置: {save['location']}")
                print(f"      状态: HP {save['hp']} | SAN {save['sanity']}\n")

            try:
                idx = int(input("请选择存档编号 (1-[最旧] ~ [最新]): ").strip()) - 1
                if 0 <= idx < len(saves):
                    session_id = saves[idx]['session_id']
                    print(f"✅ 已选择存档: {session_id}")
                else:
                    print("⚠️  无效选择，将创建新游戏\n")
                    session_id = None
            except (ValueError, IndexError):
                print("⚠️  无效输入，将创建新游戏\n")
                session_id = None

    if session_id is None:
        # 初始化新世界
        session_id = f"session_{__import__('uuid').uuid4().hex[:8]}"
        world_data = initialize_new_world()

        # 获取第一个有效的起始位置
        if world_data.get("geo_graph_l2"):
            start_location = world_data["geo_graph_l2"][0].get("region_id", "tavern_square")
        print(f"\n🏃 玩家出生地: {start_location}")

    # 初始化游戏引擎
    print(f"\n🎮 初始化游戏引擎 (Session: {session_id})...")
    llm_client = get_llm_client()
    engine = RuntimeEngine(
        session_id=session_id,
        llm_client=llm_client,
        debug_mode=True
    )

    # 加载插件系统
    engine.load_plugins()

    if session_id is None or choice != "1":
        # 新游戏或未加载存档：初始化玩家
        engine.initialize_player(
            start_location_id=start_location,
            initial_tags=["traveler", "outsider"]
        )
        print("🎭 玩家角色已创建")
    else:
        # 已加载存档：验证状态
        print("📂 正在从存档恢复...")

    # 显示初始状态
    print_player_status(engine)

    # 显示初始环境描述
    print("🌌 正在生成初始环境描述...\n")
    initial_response = engine.step("/look")
    print(initial_response)

    # 游戏主循环
    print("\n" + "═" * 60)
    print("🎬 游戏开始！输入 /help 查看帮助指令")
    print("═" * 60 + "\n")

    while True:
        try:
            user_input = input("👤 > ").strip()

            if not user_input:
                continue

            # 处理特殊命令
            if user_input.lower() in ["/quit", "/exit", "q", "exit"]:
                # 询问是否保存
                save_choice = input("💾 退出前是否保存游戏？(y/n): ").strip().lower()
                if save_choice == 'y' or save_choice == 'yes':
                    save_game(engine)
                print("\n👋 感谢游玩，再见！")
                break

            elif user_input.lower() == "/help" or user_input.lower() == "h":
                print_help()
                continue

            elif user_input.lower() == "/status":
                show_character_status(engine)
                continue

            elif user_input.lower() == "/map":
                show_map_summary(engine)
                continue

            elif user_input.lower() == "/save":
                save_game(engine)
                continue

            elif user_input.lower() == "/load":
                load_game(engine)
                continue

            elif user_input.lower() == "/exits":
                list_exits(engine)
                continue

            elif user_input.lower() == "/events":
                print("\n📜 游戏事件记录:")
                print("=" * 50)
                events = engine.event_system.get_all_events()
                if events:
                    for event in events:
                        print(f"  {event['timestamp']}: {event['type']} - {event['name']}")
                        print(f"    {event['description']}")
                        print()
                else:
                    print("  暂无事件记录")
                continue

            elif user_input.lower() == "/world":
                print("\n🌍 世界状态:")
                print("=" * 50)
                world_state = engine.world_state.get_world_summary()
                for key, value in world_state.items():
                    print(f"  {key}: {value}")
                continue

            elif user_input.lower() == "/plugins":
                print("\n🔌 已加载插件:")
                print("=" * 50)
                plugins = engine.plugin_manager.list_plugins()
                if plugins:
                    for plugin, hooks in plugins.items():
                        print(f"  {plugin}:")
                        for hook in hooks:
                            print(f"    - {hook}")
                else:
                    print("  暂无插件加载")
                continue

            # 处理游戏指令
            response = engine.step(user_input)
            print(f"\n{response}\n")

            # 检查游戏结束条件
            state = engine.cognition.get_player_state()
            if state.get('hp', 100) <= 0:
                print("💀 你已经死亡...")
                print("游戏结束。")
                break
            if state.get('sanity', 100) <= 0:
                print("🌀 你的理智已经完全崩溃...")
                print("游戏结束。")
                break

            # 移动成功后更新状态显示
            if user_input.startswith("/move") or user_input.startswith("/look"):
                print_player_status(engine)

        except KeyboardInterrupt:
            print("\n\n⚠️  游戏被中断")
            save_choice = input("💾  是否保存当前进度？(y/n): ").strip().lower()
            if save_choice == 'y' or save_choice == 'yes':
                save_game(engine)
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    main()