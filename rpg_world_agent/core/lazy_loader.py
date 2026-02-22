"""
Lazy Loader - 懒加载优化系统

这个系统减少不必要的 LLM 调用，通过：
1. 缓存已生成的内容
2. 智能判断是否需要调用 LLM
3. 相似内容复用
4. API 调用频率控制

核心功能：
- should_generate_content(): 判断是否需要生成新内容
- get_cached_or_generate(): 获取缓存或生成新内容
- find_similar_content(): 查找相似内容
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum

from rpg_world_agent.core.event_system import EventSystem
from rpg_world_agent.core.world_state import WorldStateManager

if TYPE_CHECKING:
    from rpg_world_agent.core.runtime import RuntimeEngine


class ContentType(Enum):
    """内容类型"""
    LOCATION = "location"
    NPC = "npc"
    ITEM = "item"
    QUEST = "quest"
    DIALOGUE = "dialogue"
    NARRATIVE = "narrative"
    DESCRIPTION = "description"
    CUSTOM = "custom"


class GenerationReason(Enum):
    """生成原因"""
    CACHE_MISS = "cache_miss"           # 缓存未命中
    STALE_CACHE = "stale_cache"         # 缓存过期
    FORCE_REFRESH = "force_refresh"     # 强制刷新
    CONTEXT_CHANGE = "context_change"   # 上下文变化
    NEW_REQUEST = "new_request"         # 新请求
    NO_SIMILAR = "no_similar"           # 无相似内容


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    content_type: ContentType
    content: Any
    context_hash: str                  # 生成时的上下文哈希
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl_seconds: int = 3600            # 默认 1 小时
    tags: Set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.created_at > self.ttl_seconds

    def is_context_valid(self, current_context_hash: str) -> bool:
        """检查上下文是否仍然有效"""
        return self.context_hash == current_context_hash


@dataclass
class LoadContext:
    """加载上下文"""
    player_id: str
    location: str
    world_state: WorldStateManager
    event_system: EventSystem
    extra: Dict[str, Any] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """计算上下文哈希"""
        data = {
            "player_id": self.player_id,
            "location": self.location,
            "crisis_level": self.world_state.crisis_level.value,
            "time": self.world_state.world_time.total_minutes // 60,  # 按小时聚合
            "flags": sorted(self.world_state.global_flags.keys())
        }
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(json_str.encode()).hexdigest()


@dataclass
class LazyLoadingConfig:
    """懒加载配置"""
    # 缓存设置
    cache_ttl_default: int = 3600              # 默认缓存时间（秒）
    cache_ttl_location: int = 7200             # 地点缓存时间
    cache_ttl_npc: int = 1800                  # NPC 缓存时间
    cache_ttl_narrative: int = 300             # 叙事缓存时间（较短）
    max_cache_size: int = 1000                 # 最大缓存条目数

    # 相似度阈值
    similarity_threshold: float = 0.8          # 相似度阈值（0-1）

    # API 调用控制
    max_calls_per_minute: int = 20             # 每分钟最大调用次数
    min_interval_ms: int = 100                 # 最小调用间隔（毫秒）

    # 懒加载策略
    reuse_similar_content: bool = True         # 是否复用相似内容
    context_aware_caching: bool = True         # 是否启用上下文感知缓存
    smart_expiration: bool = True              # 是否智能过期


class ContentCache:
    """
    内容缓存

    存储生成的各种内容，支持：
    - 按类型存储
    - TTL 过期
    - 上下文验证
    - LRU 淘汰
    """

    def __init__(self, config: Optional[LazyLoadingConfig] = None):
        self.config = config or LazyLoadingConfig()
        self._cache: Dict[str, CacheEntry] = {}
        self._type_index: Dict[ContentType, Set[str]] = {t: set() for t in ContentType}

    def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存条目"""
        entry = self._cache.get(key)
        if entry:
            entry.last_accessed = time.time()
            entry.access_count += 1
        return entry

    def set(
        self,
        key: str,
        content: Any,
        content_type: ContentType,
        context_hash: str,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """设置缓存条目"""
        # 检查容量，必要时淘汰
        if len(self._cache) >= self.config.max_cache_size:
            self._evict_lru()

        ttl = ttl_seconds or self._get_default_ttl(content_type)

        entry = CacheEntry(
            key=key,
            content_type=content_type,
            content=content,
            context_hash=context_hash,
            created_at=time.time(),
            last_accessed=time.time(),
            ttl_seconds=ttl,
            tags=tags or set()
        )

        # 删除旧条目（如果存在）
        if key in self._cache:
            old_entry = self._cache[key]
            self._type_index[old_entry.content_type].discard(key)

        self._cache[key] = entry
        self._type_index[content_type].add(key)

    def delete(self, key: str) -> bool:
        """删除缓存条目"""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._type_index[entry.content_type].discard(key)
            return True
        return False

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        for type_set in self._type_index.values():
            type_set.clear()

    def get_by_type(self, content_type: ContentType) -> List[CacheEntry]:
        """按类型获取缓存条目"""
        keys = self._type_index.get(content_type, set())
        entries = []
        for key in list(keys):  # 复制以防迭代时修改
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                entries.append(entry)
        return entries

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            self.delete(key)
        return len(expired_keys)

    def _evict_lru(self) -> None:
        """淘汰最久未使用的条目"""
        if not self._cache:
            return

        # 找到最久未使用的条目
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].access_count, self._cache[k].last_accessed)
        )
        self.delete(lru_key)

    def _get_default_ttl(self, content_type: ContentType) -> int:
        """获取内容类型的默认 TTL"""
        ttl_map = {
            ContentType.LOCATION: self.config.cache_ttl_location,
            ContentType.NPC: self.config.cache_ttl_npc,
            ContentType.NARRATIVE: self.config.cache_ttl_narrative,
        }
        return ttl_map.get(content_type, self.config.cache_ttl_default)


class SimilarityMatcher:
    """
    相似度匹配器

    用于查找相似的内容，避免重复生成
    """

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold

    def find_similar(
        self,
        query: str,
        candidates: List[CacheEntry],
        top_k: int = 3
    ) -> List[Tuple[CacheEntry, float]]:
        """
        查找相似内容

        Args:
            query: 查询字符串
            candidates: 候选缓存条目
            top_k: 返回的最大数量

        Returns:
            List[Tuple[CacheEntry, float]]: (条目, 相似度) 列表
        """
        results: List[Tuple[CacheEntry, float]] = []

        for entry in candidates:
            if isinstance(entry.content, str):
                similarity = self._compute_similarity(query, entry.content)
            elif isinstance(entry.content, dict):
                # 对字典内容，计算描述字段的相似度
                desc = entry.content.get("description", "")
                name = entry.content.get("name", "")
                combined = f"{name} {desc}"
                similarity = self._compute_similarity(query, combined)
            else:
                continue

            if similarity >= self.threshold:
                results.append((entry, similarity))

        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度

        使用简化的 Jaccard 相似度（基于词集合）
        """
        # 分词（简化实现）
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        # Jaccard 相似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0


class RateLimiter:
    """
    API 调用频率限制器

    控制 LLM 调用频率
    """

    def __init__(self, max_calls_per_minute: int = 20, min_interval_ms: int = 100):
        self.max_calls_per_minute = max_calls_per_minute
        self.min_interval_ms = min_interval_ms
        self._call_times: List[float] = []

    def can_call(self) -> bool:
        """检查是否可以调用"""
        now = time.time()

        # 清理 1 分钟前的记录
        cutoff = now - 60
        self._call_times = [t for t in self._call_times if t > cutoff]

        # 检查调用次数
        if len(self._call_times) >= self.max_calls_per_minute:
            return False

        # 检查最小间隔
        if self._call_times:
            last_call = self._call_times[-1]
            if (now - last_call) * 1000 < self.min_interval_ms:
                return False

        return True

    def record_call(self) -> None:
        """记录一次调用"""
        self._call_times.append(time.time())

    def wait_time(self) -> float:
        """获取需要等待的秒数"""
        if self.can_call():
            return 0.0

        now = time.time()

        # 计算到下一次可用的时间
        if len(self._call_times) >= self.max_calls_per_minute:
            oldest = self._call_times[0]
            return max(0, 60 - (now - oldest))

        if self._call_times:
            last_call = self._call_times[-1]
            wait = (self.min_interval_ms / 1000) - (now - last_call)
            return max(0, wait)

        return 0.0


class LazyLoadingStrategy:
    """
    懒加载策略

    决定何时生成新内容，何时复用缓存
    """

    def __init__(
        self,
        config: Optional[LazyLoadingConfig] = None,
        cache: Optional[ContentCache] = None
    ):
        self.config = config or LazyLoadingConfig()
        self.cache = cache or ContentCache(self.config)
        self.similarity_matcher = SimilarityMatcher(self.config.similarity_threshold)
        self.rate_limiter = RateLimiter(
            self.config.max_calls_per_minute,
            self.config.min_interval_ms
        )

        # 统计信息
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "similar_reused": 0,
            "calls_blocked": 0,
            "total_calls": 0
        }

    def should_generate_content(
        self,
        key: str,
        context: LoadContext,
        content_type: ContentType,
        force: bool = False
    ) -> Tuple[bool, GenerationReason]:
        """
        判断是否应该生成新内容

        Args:
            key: 内容键
            context: 加载上下文
            content_type: 内容类型
            force: 是否强制生成

        Returns:
            Tuple[bool, GenerationReason]: (是否生成, 原因)
        """
        self._stats["total_calls"] += 1

        # 强制生成
        if force:
            return True, GenerationReason.FORCE_REFRESH

        # 检查缓存
        cached = self.cache.get(key)

        # 缓存未命中
        if not cached:
            self._stats["cache_misses"] += 1
            return True, GenerationReason.CACHE_MISS

        # 缓存过期
        if cached.is_expired():
            self._stats["cache_misses"] += 1
            return True, GenerationReason.STALE_CACHE

        # 上下文变化（如果启用上下文感知）
        if self.config.context_aware_caching:
            current_hash = context.compute_hash()
            if not cached.is_context_valid(current_hash):
                self._stats["cache_misses"] += 1
                return True, GenerationReason.CONTEXT_CHANGE

        # 缓存命中
        self._stats["cache_hits"] += 1
        return False, GenerationReason.CACHE_MISS

    def get_cached_or_generate(
        self,
        key: str,
        context: LoadContext,
        content_type: ContentType,
        generator: Callable[[], Any],
        force: bool = False
    ) -> Tuple[Any, bool]:
        """
        获取缓存或生成新内容

        Args:
            key: 内容键
            context: 加载上下文
            content_type: 内容类型
            generator: 内容生成函数
            force: 是否强制生成

        Returns:
            Tuple[Any, bool]: (内容, 是否新生成)
        """
        # 首先检查相似内容（如果启用）
        if self.config.reuse_similar_content and not force:
            # 这里可以传入查询词，但简化实现中跳过
            pass

        # 判断是否需要生成
        should_generate, reason = self.should_generate_content(
            key, context, content_type, force
        )

        if should_generate:
            # 检查频率限制
            if not self.rate_limiter.can_call():
                self._stats["calls_blocked"] += 1
                # 返回缓存的旧内容（即使过期）
                cached = self.cache.get(key)
                if cached:
                    return cached.content, False
                # 没有缓存，必须等待
                return None, False

            # 生成新内容
            content = generator()
            self.rate_limiter.record_call()

            # 存入缓存
            context_hash = context.compute_hash() if self.config.context_aware_caching else ""
            self.cache.set(
                key=key,
                content=content,
                content_type=content_type,
                context_hash=context_hash
            )

            return content, True

        # 返回缓存
        cached = self.cache.get(key)
        return cached.content if cached else None, False

    def find_similar_content(
        self,
        query: str,
        content_type: ContentType,
        threshold: Optional[float] = None
    ) -> Optional[Tuple[Any, float]]:
        """
        查找相似内容

        Args:
            query: 查询字符串
            content_type: 内容类型
            threshold: 相似度阈值

        Returns:
            Optional[Tuple[Any, float]]: (内容, 相似度) 或 None
        """
        if not self.config.reuse_similar_content:
            return None

        old_threshold = self.similarity_matcher.threshold
        if threshold is not None:
            self.similarity_matcher.threshold = threshold

        candidates = self.cache.get_by_type(content_type)
        results = self.similarity_matcher.find_similar(query, candidates, top_k=1)

        self.similarity_matcher.threshold = old_threshold

        if results:
            entry, similarity = results[0]
            self._stats["similar_reused"] += 1
            return entry.content, similarity

        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._stats["cache_hits"] + self._stats["cache_misses"]
        hit_rate = self._stats["cache_hits"] / total if total > 0 else 0

        return {
            **self._stats,
            "cache_hit_rate": hit_rate,
            "cache_size": len(self.cache._cache)
        }

    def clear_cache(self) -> None:
        """清空缓存"""
        self.cache.clear()

    def cleanup(self) -> int:
        """清理过期缓存"""
        return self.cache.cleanup_expired()


# =============================================================================
# 🏭 便捷函数
# =============================================================================

def create_lazy_loader(
    max_cache_size: int = 1000,
    similarity_threshold: float = 0.8,
    max_calls_per_minute: int = 20
) -> LazyLoadingStrategy:
    """
    创建懒加载策略实例

    Args:
        max_cache_size: 最大缓存大小
        similarity_threshold: 相似度阈值
        max_calls_per_minute: 每分钟最大调用次数

    Returns:
        LazyLoadingStrategy: 懒加载策略实例
    """
    config = LazyLoadingConfig(
        max_cache_size=max_cache_size,
        similarity_threshold=similarity_threshold,
        max_calls_per_minute=max_calls_per_minute
    )
    return LazyLoadingStrategy(config=config)
