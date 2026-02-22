"""Player Character System - Attributes, Skills, and Inventory Management.

This module provides a comprehensive player character system including:
- Six D&D style attributes (STR, DEX, INT, WIS, CON, CHA)
- Skill proficiency system
- Item inventory and equipment management
- Character state management (HP, Sanity, Stamina)
"""

import json
from typing import Any, Dict, List, Optional, TypedDict

from rpg_world_agent.config.settings import AGENT_CONFIG
from rpg_world_agent.config.rules import VALID_SKILLS


# Default attribute values for point-buy (10 base)
DEFAULT_ATTRIBUTES = {
    "str": 10,  # Strength
    "dex": 10,  # Dexterity
    "int": 10,  # Intelligence
    "wis": 10,  # Wisdom
    "con": 10,  # Constitution
    "cha": 10,  # Charisma
}

# Attribute modifiers based on D&D 5e rules
ATTRIBUTE_MODIFIER = {
    1: -5, 2: -4, 3: -4, 4: -3, 5: -3, 6: -2, 7: -2, 8: -1, 9: -1,
    10: 0, 11: 0, 12: 1, 13: 1, 14: 2, 15: 2, 16: 3, 17: 3,
    18: 4, 19: 4, 20: 5, 21: 5, 22: 6, 23: 6, 24: 7, 25: 7, 26: 8,
    27: 8, 28: 9, 29: 9, 30: 10
}

# Skill to primary attribute mapping
SKILL_ATTRIBUTES = {
    "arcana": "int",
    "history": "int",
    "nature": "int",
    "religion": "int",
    "investigation": "int",
    "insight": "wis",
    "perception": "wis",
    "medicine": "wis",
    "survival": "wis",
    "persuasion": "cha",
    "deception": "cha",
    "intimidation": "cha",
    "street_wise": "cha",
    # Additional skills
    "athletics": "str",
    "acrobatics": "dex",
    "stealth": "dex",
    "sleight_of_hand": "dex",
    "performance": "cha",
    "animal_handling": "wis",
}


class InventoryItem(TypedDict):
    """物品数据结构。"""
    item_id: str
    name: str
    description: str
    count: int
    item_type: str  # weapon, armor, consumable, treasure, key_item
    value: int
    weight: float


class EquipmentSlot(TypedDict):
    """装备栏数据结构。"""
    head: Optional[str]  # item_id
    chest: Optional[str]
    hands: Optional[str]
    off_hand: Optional[str]
    legs: Optional[str]
    feet: Optional[str]
    accessory: Optional[str]


class PlayerCharacter:
    """ Comprehensive player character management system. """

    def __init__(self, character_id: str):
        self.character_id = character_id
        self._data = self._get_default_data()

    @staticmethod
    def _get_default_data() -> Dict[str, Any]:
        """获取默认角色数据。"""
        return {
            "attributes": DEFAULT_ATTRIBUTES.copy(),
            "skills": {skill: 1 for skill in VALID_SKILLS},  # Proficiency level 1-5
            "state": {
                "hp": 100,
                "max_hp": 100,
                "sanity": 100,
                "max_sanity": 100,
                "stamina": 100,
                "max_stamina": 100,
            },
            "inventory": {
                "items": [],
                "equipped": {
                    "head": None,
                    "chest": None,
                    "hands": None,
                    "off_hand": None,
                    "legs": None,
                    "feet": None,
                    "accessory": None,
                },
                "max_capacity": 20,  # 物品栏最大容量
            },
            "tags": ["traveler"],  # 身份标签
            "level": 1,
            "exp": 0,
            "gold": 100,
        }

    def get_attribute(self, attr: str) -> int:
        """获取属性值。"""
        attr = attr.lower()
        if attr not in DEFAULT_ATTRIBUTES:
            raise ValueError(f"Invalid attribute: {attr}")
        return self._data["attributes"].get(attr, 10)

    def set_attribute(self, attr: str, value: int) -> None:
        """设置属性值。"""
        attr = attr.lower()
        if attr not in DEFAULT_ATTRIBUTES:
            raise ValueError(f"Invalid attribute: {attr}")
        value = max(1, min(30, value))  # Clamp between 1-30
        self._data["attributes"][attr] = value

    def get_attribute_modifier(self, attr: str) -> int:
        """获取属性修正值。"""
        value = self.get_attribute(attr)
        return ATTRIBUTE_MODIFIER.get(value, 0)

    def get_skill_proficiency(self, skill: str) -> int:
        """获取技能熟练度 (1-5)。"""
        if skill not in VALID_SKILLS:
            raise ValueError(f"Invalid skill: {skill}")
        return self._data["skills"].get(skill, 1)

    def set_skill_proficiency(self, skill: str, level: int) -> None:
        """设置技能熟练度。"""
        if skill not in VALID_SKILLS:
            raise ValueError(f"Invalid skill: {skill}")
        level = max(1, min(5, level))
        self._data["skills"][skill] = level

    def get_skill_modifier(self, skill: str) -> int:
        """
        获取技能总修正值。

        Formula: Attribute Modifier + (Proficiency - 1)
        """
        if skill not in VALID_SKILLS:
            return 0

        attr = SKILL_ATTRIBUTES.get(skill, "int")
        attr_mod = self.get_attribute_modifier(attr)
        proficiency = self.get_skill_proficiency(skill)

        return attr_mod + (proficiency - 1)

    def get_hp(self) -> int:
        """获取当前生命值。"""
        return self._data["state"]["hp"]

    def set_hp(self, value: int) -> None:
        """设置生命值。"""
        self._data["state"]["hp"] = max(0, min(value, self.get_max_hp()))

    def get_max_hp(self) -> int:
        """获取最大生命值。"""
        return self._data["state"]["max_hp"]

    def take_damage(self, amount: int) -> int:
        """受到伤害，返回实际损失。"""
        current = self.get_hp()
        actual = min(current, amount)
        self.set_hp(current - actual)
        return actual

    def heal(self, amount: int) -> int:
        """治疗，返回实际恢复量。"""
        current = self.get_hp()
        max_hp = self.get_max_hp()
        actual = min(max_hp - current, amount)
        self.set_hp(current + actual)
        return actual

    def get_sanity(self) -> int:
        """获取当前理智值。"""
        return self._data["state"]["sanity"]

    def set_sanity(self, value: int) -> None:
        """设置理智值。"""
        self._data["state"]["sanity"] = max(0, min(value, self.get_max_sanity()))

    def get_max_sanity(self) -> int:
        """获取最大理智值。"""
        return self._data["state"]["max_sanity"]

    def lose_sanity(self, amount: int) -> int:
        """理智损失，返回实际损失。"""
        current = self.get_sanity()
        actual = min(current, amount)
        self.set_sanity(current - actual)
        return actual

    def get_stamina(self) -> int:
        """获取当前体力。"""
        return self._data["state"]["stamina"]

    def set_stamina(self, value: int) -> None:
        """设置体力。"""
        self._data["state"]["stamina"] = max(0, min(value, self.get_max_stamina()))

    def get_max_stamina(self) -> int:
        """获取最大体力。"""
        return self._data["state"]["max_stamina"]

    def consume_stamina(self, amount: int) -> bool:
        """
        消耗体力。

        Returns:
            bool: True if stamina was sufficient, False if insufficient
        """
        if self.get_stamina() >= amount:
            self.set_stamina(self.get_stamina() - amount)
            return True
        return False

    def recover_stamina(self, amount: int = 10) -> None:
        """恢复体力。"""
        self.set_stamina(self.get_stamina() + amount)

    def add_item(self, item: InventoryItem) -> bool:
        """
        添加物品到背包。

        Returns:
            bool: 成功添加返回 True，背包已满返回 False
        """
        inventory = self._data["inventory"]
        if len(inventory["items"]) >= inventory["max_capacity"]:
            return False

        # 检查是否已存在相同物品（可堆叠）
        for existing in inventory["items"]:
            if (existing["item_id"] == item["item_id"] and
                    item["item_type"] in ["consumable", "treasure"]):
                existing["count"] += item["count"]
                return True

        # 添加新物品
        inventory["items"].append(item)
        return True

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """
        从背包移除物品。

        Returns:
            bool: 成功移除返回 True，物品不足返回 False
        """
        inventory = self._data["inventory"]
        for i, item in enumerate(inventory["items"]):
            if item["item_id"] == item_id:
                if item["count"] >= count:
                    item["count"] -= count
                    if item["count"] <= 0:
                        inventory["items"].pop(i)
                    return True
                return False
        return False

    def get_item_count(self, item_id: str) -> int:
        """获取指定物品的数量。"""
        inventory = self._data["inventory"]
        for item in inventory["items"]:
            if item["item_id"] == item_id:
                return item["count"]
        return 0

    def equip_item(self, item_id: str, slot: str) -> bool:
        """
        装备物品。

        Args:
            item_id: 物品ID
            slot: 装备槽 (head, chest, hands, off_hand, legs, feet, accessory)

        Returns:
            bool: 成功装备返回 True，失败返回 False
        """
        valid_slots = ["head", "chest", "hands", "off_hand", "legs", "feet", "accessory"]
        if slot not in valid_slots:
            return False

        inventory = self._data["inventory"]
        for i, item in enumerate(inventory["items"]):
            if item["item_id"] == item_id:
                # 检查物品类型是否匹配槽位
                if not self._can_equip_in_slot(item["item_type"], slot):
                    return False

                # 卸下当前装备
                old_item = inventory["equipped"][slot]
                if old_item:
                    # 将旧装备放回背包
                    self.add_item(self._item_from_id(old_item))

                # 装备新物品
                inventory["equipped"][slot] = item_id
                inventory["items"].pop(i)
                return True

        return False

    def unequip_item(self, slot: str) -> bool:
        """卸下指定槽位的装备。"""
        valid_slots = ["head", "chest", "hands", "off_hand", "legs", "feet", "accessory"]
        if slot not in valid_slots:
            return False

        inventory = self._data["inventory"]
        item_id = inventory["equipped"][slot]
        if not item_id:
            return False

        inventory["equipped"][slot] = None
        # 简化处理：假设装备物品数据已知或持久化
        return True

    def add_tag(self, tag: str) -> None:
        """添加身份标签。"""
        if tag not in self._data["tags"]:
            self._data["tags"].append(tag)

    def has_tag(self, tag: str) -> bool:
        """检查是否拥有指定标签。"""
        return tag in self._data["tags"]

    def get_tags(self) -> List[str]:
        """获取所有身份标签。"""
        return self._data["tags"].copy()

    def add_exp(self, amount: int) -> None:
        """增加经验值。"""
        self._data["exp"] += amount
        # 简化版升级逻辑
        while self._data["exp"] >= self._data["level"] * 1000:
            self._data["exp"] -= self._data["level"] * 1000
            self._data["level"] += 1
            self._on_level_up()

    def _on_level_up(self) -> None:
        """升级时的处理。"""
        level = self._data["level"]
        # 每次升级增加属性点
        self._data["state"]["max_hp"] += 10 + self.get_attribute_modifier("con")
        self._data["state"]["hp"] = self.get_max_hp()
        print(f"⬆️ 角色升级！当前等级: {level}")

    def get_gold(self) -> int:
        """获取金币数量。"""
        return self._data["gold"]

    def add_gold(self, amount: int) -> None:
        """添加金币。"""
        self._data["gold"] = max(0, self.get_gold() + amount)

    def spend_gold(self, amount: int) -> bool:
        """花费金币。"""
        if self.get_gold() >= amount:
            self.add_gold(-amount)
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """将角色数据序列化为字典。"""
        return self._data.copy()

    def from_dict(self, data: Dict[str, Any]) -> None:
        """从字典加载角色数据。"""
        self._data = data

    def get_status_summary(self) -> str:
        """获取角色状态摘要。"""
        state = self._data["state"]
        return (
            f"❤️ HP: {state['hp']}/{state['max_hp']} | "
            f"🧠 SAN: {state['sanity']}/{state['max_sanity']} | "
            f"⚡ STAM: {state['stamina']}/{state['max_stamina']} | "
            f"💰 Gold: {self.get_gold()}"
        )

    def get_attribute_summary(self) -> str:
        """获取属性摘要。"""
        attrs = self._data["attributes"]
        return (
            f"STR: {attrs['str']} ({self.get_attribute_modifier('str'):+}) | "
            f"DEX: {attrs['dex']} ({self.get_attribute_modifier('dex'):+}) | "
            f"INT: {attrs['int']} ({self.get_attribute_modifier('int'):+}) | "
            f"WIS: {attrs['wis']} ({self.get_attribute_modifier('wis'):+}) | "
            f"CON: {attrs['con']} ({self.get_attribute_modifier('con'):+}) | "
            f"CHA: {attrs['cha']} ({self.get_attribute_modifier('cha'):+})"
        )

    def _can_equip_in_slot(self, item_type: str, slot: str) -> bool:
        """检查物品类型是否可以装备到指定槽位。"""
        slot_allowed = {
            "head": ["armor", "headgear"],
            "chest": ["armor", "clothing"],
            "hands": ["weapon", "shield", "tool"],
            "off_hand": ["weapon", "shield", "tool"],
            "legs": ["armor", "clothing"],
            "feet": ["armor", "footwear"],
            "accessory": ["accessory", "jewelry", "consumable"],
        }
        return item_type in slot_allowed.get(slot, [])

    def _item_from_id(self, item_id: str) -> InventoryItem:
        """简化处理：从物品ID创建基础物品（应从物品数据库获取）。"""
        return {
            "item_id": item_id,
            "name": item_id,
            "description": "装备描述",
            "count": 1,
            "item_type": "equipment",
            "value": 0,
            "weight": 1.0,
        }


def create_character(character_id: str, attributes: Optional[Dict[str, int]] = None,
                  skills: Optional[Dict[str, int]] = None) -> PlayerCharacter:
    """
    工厂函数：创建新角色。

    Args:
        character_id: 角色ID
        attributes: 自定义属性（可选）
        skills: 自定义技能熟练度（可选）

    Returns:
        PlayerCharacter: 创建的角色对象
    """
    char = PlayerCharacter(character_id)

    if attributes:
        for attr, value in attributes.items():
            char.set_attribute(attr, value)

    if skills:
        for skill, level in skills.items():
            if skill in VALID_SKILLS:
                char.set_skill_proficiency(skill, level)

    return char