# cache_manager.py
import hashlib
import json
import time
from typing import Any, Optional
from functools import lru_cache
import diskcache  # pip install diskcache

from internet_rumors_judge.deprecated.modern_main import ModernRumorVerificationSystem


class VerificationCache:
    """智能缓存管理器"""

    def __init__(self, use_disk_cache: bool = True):
        self.use_disk_cache = use_disk_cache

        if use_disk_cache:
            # 磁盘缓存，持久化
            self.cache = diskcache.Cache('./cache/verification')
            print("✅ 初始化磁盘缓存")
        else:
            # 内存缓存 (LRU)
            self.memory_cache = {}
            print("✅ 初始化内存缓存")

    def _generate_key(self, query: str) -> str:
        """为查询生成唯一缓存键"""
        # 使用MD5哈希，确保键长度固定
        return hashlib.md5(query.encode('utf-8')).hexdigest()

    def get(self, query: str) -> Optional[Dict]:
        """从缓存获取结果"""
        key = self._generate_key(query)

        try:
            if self.use_disk_cache:
                if key in self.cache:
                    result = self.cache[key]
                    # 检查是否过期（例如缓存1天）
                    if time.time() - result.get('_timestamp', 0) < 86400:
                        print(f"💾 缓存命中: {query[:30]}...")
                        return result['data']
            else:
                if key in self.memory_cache:
                    cached = self.memory_cache[key]
                    if time.time() - cached['_timestamp'] < 86400:
                        print(f"💾 缓存命中: {query[:30]}...")
                        return cached['data']
        except Exception as e:
            print(f"⚠️ 缓存读取错误: {e}")

        return None

    def set(self, query: str, data: Dict):
        """存储结果到缓存"""
        key = self._generate_key(query)
        cache_item = {
            'data': data,
            '_timestamp': time.time(),
            '_query': query[:100]  # 存储部分查询以便调试
        }

        try:
            if self.use_disk_cache:
                self.cache[key] = cache_item
            else:
                self.memory_cache[key] = cache_item
        except Exception as e:
            print(f"⚠️ 缓存存储错误: {e}")

    def clear_expired(self):
        """清理过期缓存"""
        if self.use_disk_cache:
            expired_count = 0
            for key in list(self.cache):
                try:
                    item = self.cache[key]
                    if time.time() - item['_timestamp'] > 86400:
                        del self.cache[key]
                        expired_count += 1
                except:
                    pass
            print(f"🗑️ 清理了 {expired_count} 个过期缓存项")


# 在主系统中集成缓存
class EnhancedRumorVerificationSystem(ModernRumorVerificationSystem):
    def __init__(self):
        super().__init__()
        self.cache = VerificationCache(use_disk_cache=True)

    def verify_with_cache(self, user_input: str) -> Dict:
        """带缓存的验证流程"""
        # 1. 检查缓存
        cached_result = self.cache.get(user_input)
        if cached_result:
            cached_result['_from_cache'] = True
            return cached_result

        # 2. 实际运行验证流程
        result = super().verify(user_input)
        result['_from_cache'] = False

        # 3. 存储到缓存（只有结论明确的才缓存）
        final_report = result.get('final_report', '')
        if '假' in final_report or '真' in final_report or '证据不足' in final_report:
            self.cache.set(user_input, result)

        return result