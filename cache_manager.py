import hashlib
from typing import Optional
from diskcache import Cache
from truth_summarizer import FinalVerdict

class CacheManager:
    def __init__(self, cache_dir: str = ".cache"):
        self.cache = Cache(cache_dir)
        # 默认缓存过期时间：24小时 (秒)
        self.default_ttl = 86400 

    def _generate_key(self, query: str) -> str:
        """生成基于查询字符串的唯一键"""
        # 规范化查询：去除首尾空格，转小写，确保同一问题的不同形式能命中缓存
        normalized_query = query.strip().lower()
        return hashlib.md5(normalized_query.encode('utf-8')).hexdigest()

    def get_verdict(self, query: str) -> Optional[FinalVerdict]:
        """尝试获取缓存的裁决结果"""
        key = self._generate_key(query)
        data = self.cache.get(key)
        
        if data:
            try:
                # 反序列化为 FinalVerdict 对象
                return FinalVerdict(**data)
            except Exception as e:
                print(f"⚠️ 缓存反序列化失败: {e}")
                return None
        return None

    def set_verdict(self, query: str, verdict: FinalVerdict, ttl: Optional[int] = None):
        """缓存裁决结果"""
        if not verdict:
            return
            
        key = self._generate_key(query)
        # 序列化为字典
        data = verdict.model_dump()
        self.cache.set(key, data, expire=ttl or self.default_ttl)

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def close(self):
        """关闭缓存连接"""
        self.cache.close()
