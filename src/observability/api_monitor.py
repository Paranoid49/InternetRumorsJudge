"""
API监控模块

提供API使用量、成本和配额监控功能
- API调用统计
- Token使用量追踪
- 成本计算
- 配额监控
- 告警机制
"""
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path
from threading import Lock
from collections import defaultdict

logger = logging.getLogger("APIMonitor")


class APIUsageRecord:
    """API使用记录"""

    def __init__(
        self,
        timestamp: datetime,
        provider: str,
        model: str,
        endpoint: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        cost: float = 0.0
    ):
        self.timestamp = timestamp
        self.provider = provider
        self.model = model
        self.endpoint = endpoint
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        self.cost = cost

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'provider': self.provider,
            'model': self.model,
            'endpoint': self.endpoint,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'cost': self.cost
        }


class QuotaConfig:
    """配额配置"""

    def __init__(
        self,
        daily_budget: Optional[float] = None,
        monthly_budget: Optional[float] = None,
        daily_token_limit: Optional[int] = None,
        monthly_token_limit: Optional[int] = None,
        alert_threshold: float = 0.8  # 达到配额80%时告警
    ):
        self.daily_budget = daily_budget
        self.monthly_budget = monthly_budget
        self.daily_token_limit = daily_token_limit
        self.monthly_token_limit = monthly_token_limit
        self.alert_threshold = alert_threshold


class APIMonitor:
    """
    API监控器

    职责：
    1. 记录API调用
    2. 计算成本
    3. 监控配额
    4. 生成告警
    5. 生成报告
    """

    # 各模型的价格（每1K tokens）
    PRICING = {
        'dashscope': {
            'qwen-plus': {'input': 0.0004, 'output': 0.002},
            'qwen-max': {'input': 0.02, 'output': 0.06},
            'qwen-turbo': {'input': 0.0003, 'output': 0.0006},
            'text-embedding-v4': {'input': 0.0007, 'output': 0},  # 仅输入计费
        },
        'tavily': {
            'search': {'per_request': 0.005}  # 每次搜索固定费用
        }
    }

    def __init__(self, quota_config: Optional[QuotaConfig] = None):
        """
        初始化API监控器

        Args:
            quota_config: 配额配置
        """
        self._lock = Lock()
        self._quota_config = quota_config

        # 使用记录（按时间存储）
        self._records: List[APIUsageRecord] = []

        # 统计数据（按日期和模型）
        self._daily_stats: Dict[str, Dict] = defaultdict(lambda: {
            'total_cost': 0.0,
            'total_tokens': 0,
            'api_calls': 0
        })

        # 告警记录
        self._alerts: List[Dict] = []

        # 持久化路径
        self._data_dir = Path(os.getenv('API_MONITOR_DATA_DIR', 'data/api_monitor'))
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # 加载历史数据
        self._load_historical_data()

        logger.info("API监控器初始化完成")

    def _load_historical_data(self):
        """加载历史数据"""
        try:
            # 加载使用记录
            records_file = self._data_dir / 'usage_records.jsonl'
            if records_file.exists():
                with open(records_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            record = APIUsageRecord(
                                timestamp=datetime.fromisoformat(data['timestamp']),
                                provider=data['provider'],
                                model=data['model'],
                                endpoint=data['endpoint'],
                                input_tokens=data.get('input_tokens', 0),
                                output_tokens=data.get('output_tokens', 0),
                                total_tokens=data.get('total_tokens', 0),
                                cost=data.get('cost', 0.0)
                            )
                            self._records.append(record)

            # 加载统计数据
            stats_file = self._data_dir / 'daily_stats.json'
            if stats_file.exists():
                with open(stats_file, 'r', encoding='utf-8') as f:
                    loaded_stats = json.load(f)
                    # 更新到 defaultdict 中，保持 defaultdict 的特性
                    for date_key, value in loaded_stats.items():
                        self._daily_stats[date_key] = value

            logger.info(f"加载历史数据: {len(self._records)} 条记录")

        except Exception as e:
            logger.warning(f"加载历史数据失败: {e}")

    def record_api_call(
        self,
        provider: str,
        model: str,
        endpoint: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: Optional[int] = None
    ) -> float:
        """
        记录API调用

        Args:
            provider: 提供商 (dashscope, tavily)
            model: 模型名称
            endpoint: 端点/操作类型
            input_tokens: 输入token数
            output_tokens: 输出token数
            total_tokens: 总token数（如果提供，优先使用）

        Returns:
            成本（元）
        """
        try:
            with self._lock:
                timestamp = datetime.now()

                # 计算总token数
                if total_tokens is None:
                    total_tokens = input_tokens + output_tokens

                # 计算成本
                cost = self._calculate_cost(provider, model, input_tokens, output_tokens)

                # 创建记录
                record = APIUsageRecord(
                    timestamp=timestamp,
                    provider=provider,
                    model=model,
                    endpoint=endpoint,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost
                )

                # 添加记录
                self._records.append(record)

                # 更新统计
                date_key = timestamp.strftime('%Y-%m-%d')
                self._daily_stats[date_key]['total_cost'] += cost
                self._daily_stats[date_key]['total_tokens'] += total_tokens
                self._daily_stats[date_key]['api_calls'] += 1

                # 检查配额（可能抛出异常）
                try:
                    self._check_quota(date_key)
                except Exception as e:
                    logger.error(f"检查配额时出错 (date={date_key}): {e}")

                # 持久化（可能抛出异常）
                try:
                    self._persist_record(record)
                except Exception as e:
                    logger.error(f"持久化记录时出错: {e}")

                try:
                    self._persist_stats()
                except Exception as e:
                    logger.error(f"持久化统计时出错: {e}")

                logger.debug(
                    f"API调用记录: {provider}/{model} - "
                    f"tokens={total_tokens}, cost={cost:.6f}元"
                )

                return cost

        except Exception as e:
            logger.error(f"记录 API 调用时发生错误: {e}, provider={provider}, model={model}")
            # 即使出错，也尝试返回一个合理的成本值
            return self._calculate_cost(provider, model, input_tokens, output_tokens)

    def _calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        计算API调用成本

        Args:
            provider: 提供商
            model: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数

        Returns:
            成本（元）
        """
        if provider not in self.PRICING:
            logger.warning(f"未知的提供商: {provider}")
            return 0.0

        if model not in self.PRICING[provider]:
            logger.warning(f"未知的模型: {provider}/{model}")
            return 0.0

        pricing = self.PRICING[provider][model]

        # 特殊处理Tavily（按请求计费）
        if 'per_request' in pricing:
            return pricing['per_request']

        # 标准的token计费
        input_cost = (input_tokens / 1000) * pricing['input']
        output_cost = (output_tokens / 1000) * pricing['output']
        total_cost = input_cost + output_cost

        return total_cost

    def _check_quota(self, date_key: str):
        """
        检查配额并生成告警

        Args:
            date_key: 日期键（YYYY-MM-DD）
        """
        if not self._quota_config:
            return

        stats = self._daily_stats[date_key]

        # 检查每日预算
        if self._quota_config.daily_budget:
            usage_ratio = stats['total_cost'] / self._quota_config.daily_budget
            if usage_ratio >= 1.0:
                self._create_alert(
                    level='critical',
                    message=f"每日预算已超支！已用: {stats['total_cost']:.2f}元, "
                           f"预算: {self._quota_config.daily_budget:.2f}元"
                )
            elif usage_ratio >= self._quota_config.alert_threshold:
                self._create_alert(
                    level='warning',
                    message=f"每日预算使用已达{usage_ratio*100:.0f}%。"
                           f"已用: {stats['total_cost']:.2f}元, "
                           f"预算: {self._quota_config.daily_budget:.2f}元"
                )

        # 检查每日token限制
        if self._quota_config.daily_token_limit:
            token_ratio = stats['total_tokens'] / self._quota_config.daily_token_limit
            if token_ratio >= 1.0:
                self._create_alert(
                    level='critical',
                    message=f"每日token额度已超支！已用: {stats['total_tokens']}, "
                           f"限制: {self._quota_config.daily_token_limit}"
                )
            elif token_ratio >= self._quota_config.alert_threshold:
                self._create_alert(
                    level='warning',
                    message=f"每日token使用已达{token_ratio*100:.0f}%。"
                           f"已用: {stats['total_tokens']}, "
                           f"限制: {self._quota_config.daily_token_limit}"
                )

    def _create_alert(self, level: str, message: str):
        """
        创建告警

        Args:
            level: 告警级别 (info, warning, critical)
            message: 告警消息
        """
        # 验证告警级别
        valid_levels = ['info', 'warning', 'critical']
        if level not in valid_levels:
            logger.warning(f"无效的告警级别: {level}, 使用 'info' 作为默认值")
            level = 'info'

        # 验证消息
        if not isinstance(message, str):
            logger.warning(f"告警消息不是字符串类型: {type(message)}, 转换为字符串")
            message = str(message)

        alert = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }

        self._alerts.append(alert)

        # 记录日志
        log_func_map = {
            'info': logger.info,
            'warning': logger.warning,
            'critical': logger.error
        }
        log_func = log_func_map.get(level, logger.info)
        log_func(f"[API监控告警] {level.upper()}: {message}")

    def _persist_record(self, record: APIUsageRecord):
        """
        持久化使用记录

        Args:
            record: 使用记录
        """
        try:
            records_file = self._data_dir / 'usage_records.jsonl'
            record_dict = record.to_dict()
            # 确保时间戳是字符串格式
            if 'timestamp' in record_dict and hasattr(record_dict['timestamp'], 'isoformat'):
                record_dict['timestamp'] = record_dict['timestamp'].isoformat()

            with open(records_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record_dict, ensure_ascii=False) + '\n')
        except (TypeError, ValueError) as e:
            logger.error(f"持久化使用记录失败: {e}, 记录类型: {type(record)}")
        except Exception as e:
            logger.error(f"持久化使用记录时发生未知错误: {e}")

    def _persist_stats(self):
        """持久化统计数据"""
        try:
            stats_file = self._data_dir / 'daily_stats.json'
            # 转换为普通字典，确保所有值都是 JSON 可序列化的
            stats_to_save = {}
            for date_key, value in self._daily_stats.items():
                # 确保 value 是普通字典，不是 defaultdict 或其他特殊类型
                stats_to_save[date_key] = dict(value) if hasattr(value, 'items') else value

            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_to_save, f, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            logger.error(f"持久化统计数据失败: {e}, 数据类型: {type(self._daily_stats)}")
        except Exception as e:
            logger.error(f"持久化统计数据时发生未知错误: {e}")

    def get_daily_summary(self, date: Optional[datetime] = None) -> Dict:
        """
        获取每日汇总

        Args:
            date: 日期，默认为今天

        Returns:
            汇总信息字典
        """
        if date is None:
            date = datetime.now()

        date_key = date.strftime('%Y-%m-%d')

        if date_key not in self._daily_stats:
            return {
                'date': date_key,
                'total_cost': 0.0,
                'total_tokens': 0,
                'api_calls': 0,
                'by_model': {}
            }

        stats = self._daily_stats[date_key].copy()

        # 按模型统计
        by_model = defaultdict(lambda: {'cost': 0.0, 'tokens': 0, 'calls': 0})
        for record in self._records:
            if record.timestamp.strftime('%Y-%m-%d') == date_key:
                by_model[record.model]['cost'] += record.cost
                by_model[record.model]['tokens'] += record.total_tokens
                by_model[record.model]['calls'] += 1

        stats['date'] = date_key
        stats['by_model'] = dict(by_model)

        return stats

    def get_monthly_summary(self, year: Optional[int] = None, month: Optional[int] = None) -> Dict:
        """
        获取每月汇总

        Args:
            year: 年份，默认为当前年
            month: 月份，默认为当前月

        Returns:
            汇总信息字典
        """
        now = datetime.now()
        if year is None:
            year = now.year
        if month is None:
            month = now.month

        total_cost = 0.0
        total_tokens = 0
        api_calls = 0

        # 按模型统计
        by_model = defaultdict(lambda: {'cost': 0.0, 'tokens': 0, 'calls': 0})

        # 遍历当月所有日期
        for day in range(1, 32):
            try:
                date_key = f"{year}-{month:02d}-{day:02d}"
                if date_key in self._daily_stats:
                    stats = self._daily_stats[date_key]
                    total_cost += stats['total_cost']
                    total_tokens += stats['total_tokens']
                    api_calls += stats['api_calls']
            except ValueError:
                # 日期无效（如2月30日）
                pass

        # 按模型统计
        for record in self._records:
            if record.timestamp.year == year and record.timestamp.month == month:
                by_model[record.model]['cost'] += record.cost
                by_model[record.model]['tokens'] += record.total_tokens
                by_model[record.model]['calls'] += 1

        return {
            'year': year,
            'month': month,
            'total_cost': total_cost,
            'total_tokens': total_tokens,
            'api_calls': api_calls,
            'by_model': dict(by_model)
        }

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的告警

        Args:
            limit: 返回数量

        Returns:
            告警列表
        """
        return self._alerts[-limit:]

    def generate_report(self, days: int = 7) -> str:
        """
        生成监控报告

        Args:
            days: 报告天数

        Returns:
            报告文本
        """
        lines = []
        lines.append("=" * 60)
        lines.append("API使用监控报告")
        lines.append("=" * 60)
        lines.append("")

        # 每日汇总
        now = datetime.now()
        for i in range(days):
            date = now - timedelta(days=days - i - 1)
            summary = self.get_daily_summary(date)

            lines.append(f"日期: {summary['date']}")
            lines.append(f"  总成本: {summary['total_cost']:.4f}元")
            lines.append(f"  总tokens: {summary['total_tokens']:,}")
            lines.append(f"  API调用: {summary['api_calls']}次")

            if summary['by_model']:
                lines.append("  按模型统计:")
                for model, stats in summary['by_model'].items():
                    lines.append(f"    - {model}: {stats['cost']:.4f}元, {stats['tokens']:,}tokens, {stats['calls']}次")

            lines.append("")

        # 最近告警
        alerts = self.get_recent_alerts(5)
        if alerts:
            lines.append("最近告警:")
            for alert in alerts:
                lines.append(f"  [{alert['level'].upper()}] {alert['timestamp']}: {alert['message']}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    def reset_daily_stats(self, date: Optional[datetime] = None):
        """
        重置指定日期的统计数据

        Args:
            date: 日期，默认为今天
        """
        if date is None:
            date = datetime.now()

        date_key = date.strftime('%Y-%m-%d')

        with self._lock:
            if date_key in self._daily_stats:
                del self._daily_stats[date_key]
                self._persist_stats()
                logger.info(f"已重置 {date_key} 的统计数据")


# 全局API监控器实例
_global_monitor: Optional[APIMonitor] = None
_monitor_lock = Lock()


def get_api_monitor(quota_config: Optional[QuotaConfig] = None) -> APIMonitor:
    """
    获取全局API监控器实例

    Args:
        quota_config: 配额配置

    Returns:
        APIMonitor实例
    """
    global _global_monitor

    with _monitor_lock:
        if _global_monitor is None:
            # 尝试从环境变量读取配置
            if quota_config is None:
                daily_budget = os.getenv('API_DAILY_BUDGET')
                monthly_budget = os.getenv('API_MONTHLY_BUDGET')
                daily_tokens = os.getenv('API_DAILY_TOKEN_LIMIT')
                monthly_tokens = os.getenv('API_MONTHLY_TOKEN_LIMIT')
                alert_threshold = os.getenv('API_ALERT_THRESHOLD', '0.8')

                if any([daily_budget, monthly_budget, daily_tokens, monthly_tokens]):
                    quota_config = QuotaConfig(
                        daily_budget=float(daily_budget) if daily_budget else None,
                        monthly_budget=float(monthly_budget) if monthly_budget else None,
                        daily_token_limit=int(daily_tokens) if daily_tokens else None,
                        monthly_token_limit=int(monthly_tokens) if monthly_tokens else None,
                        alert_threshold=float(alert_threshold)
                    )

            _global_monitor = APIMonitor(quota_config)

        return _global_monitor
