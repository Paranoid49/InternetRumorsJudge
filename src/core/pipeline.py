import logging
import threading
import concurrent.futures
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入线程安全工具
try:
    from src.core.thread_utils import get_lock_manager, ThreadSafeLazyLoader
    THREAD_UTILS_AVAILABLE = True
except ImportError:
    THREAD_UTILS_AVAILABLE = False

# 修复控制台中文乱码
try:
    from src.utils import encoding_fix
except ImportError:
    pass

# [v1.2.0] 统一日志配置 - 使用 observability 模块的配置
from src.observability.logger_config import configure_logging, get_logger
configure_logging()  # 使用环境变量配置

logger = get_logger("RumorJudgeEngine")

# --- 核心数据模型 (Core Data Models) ---

class PipelineStage(str, Enum):
    CACHE_CHECK = "cache_check"
    PARSING = "parsing"
    RETRIEVAL = "retrieval"
    WEB_SEARCH = "web_search"
    ANALYSIS = "analysis"
    VERDICT = "verdict"

class ProcessingMetadata(BaseModel):
    """处理过程元数据"""
    stage: PipelineStage
    success: bool
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)

class UnifiedVerificationResult(BaseModel):
    """统一的核查结果对象"""
    query: str
    is_cached: bool = False
    is_fallback: bool = False
    is_web_search: bool = False
    saved_to_cache: bool = False
    
    # 解析阶段
    entity: Optional[str] = None
    claim: Optional[str] = None
    category: Optional[str] = None
    
    # 检索阶段
    retrieved_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 分析阶段
    evidence_assessments: List[Any] = Field(default_factory=list) # List[EvidenceAssessment]
    
    # 结论阶段
    final_verdict: Optional[str] = None
    confidence_score: int = 0
    risk_level: Optional[str] = None
    summary_report: Optional[str] = None
    
    # 元数据
    metadata: List[ProcessingMetadata] = Field(default_factory=list)

    def add_metadata(self, stage: PipelineStage, success: bool, error: str = None, duration: float = 0):
        self.metadata.append(ProcessingMetadata(
            stage=stage,
            success=success,
            error_message=error,
            duration_ms=duration
        ))

# --- 导入业务组件 ---
# [v0.7.2] 重构导入逻辑：消除重复代码，提高可维护性

def _import_core_components():
    """
    统一导入核心业务组件

    将所有必需的组件导入集中在此函数中，避免重复代码。
    如果导入失败，将抛出 ImportError。
    """
    from src import config
    from src.analyzers.query_parser import build_chain as build_parser_chain
    from src.analyzers.query_parser import QueryAnalysis
    from src.retrievers.evidence_retriever import EvidenceKnowledgeBase
    from src.analyzers.evidence_analyzer import analyze_evidence, EvidenceAssessment
    from src.analyzers.truth_summarizer import summarize_truth, FinalVerdict, VerdictType, summarize_with_fallback
    from src.core.cache_manager import CacheManager
    from src.retrievers.web_search_tool import WebSearchTool
    from src.knowledge.knowledge_integrator import KnowledgeIntegrator
    from src.retrievers.hybrid_retriever import HybridRetriever

    return {
        'config': config,
        'build_parser_chain': build_parser_chain,
        'QueryAnalysis': QueryAnalysis,
        'EvidenceKnowledgeBase': EvidenceKnowledgeBase,
        'analyze_evidence': analyze_evidence,
        'EvidenceAssessment': EvidenceAssessment,
        'summarize_truth': summarize_truth,
        'FinalVerdict': FinalVerdict,
        'VerdictType': VerdictType,
        'summarize_with_fallback': summarize_with_fallback,
        'CacheManager': CacheManager,
        'WebSearchTool': WebSearchTool,
        'KnowledgeIntegrator': KnowledgeIntegrator,
        'HybridRetriever': HybridRetriever,
    }

def _import_observability():
    """
    导入可观测性模块（可选）

    Returns:
        tuple: (是否可用, 模块组件字典)
    """
    try:
        from src.observability import get_logger, get_metrics_collector, RequestContext, StageTimer
        return True, {
            'get_logger': get_logger,
            'get_metrics_collector': get_metrics_collector,
            'RequestContext': RequestContext,
            'StageTimer': StageTimer,
        }
    except ImportError:
        return False, {}

# 执行导入
try:
    _components = _import_core_components()
    # 将组件添加到全局命名空间（保持向后兼容）
    config = _components['config']
    build_parser_chain = _components['build_parser_chain']
    QueryAnalysis = _components['QueryAnalysis']
    EvidenceKnowledgeBase = _components['EvidenceKnowledgeBase']
    analyze_evidence = _components['analyze_evidence']
    EvidenceAssessment = _components['EvidenceAssessment']
    summarize_truth = _components['summarize_truth']
    FinalVerdict = _components['FinalVerdict']
    VerdictType = _components['VerdictType']
    summarize_with_fallback = _components['summarize_with_fallback']
    CacheManager = _components['CacheManager']
    WebSearchTool = _components['WebSearchTool']
    KnowledgeIntegrator = _components['KnowledgeIntegrator']
    HybridRetriever = _components['HybridRetriever']

    # 导入可观测性模块（可选）
    OBSERVABILITY_AVAILABLE, _observability = _import_observability()
    if OBSERVABILITY_AVAILABLE:
        get_logger = _observability['get_logger']
        get_metrics_collector = _observability['get_metrics_collector']
        RequestContext = _observability['RequestContext']
        StageTimer = _observability['StageTimer']

except ImportError as e:
    logger.error(f"核心组件导入失败: {e}")
    raise

class RumorJudgeEngine:
    """
    谣言核查核心引擎

    职责:
    1. 编排 pipeline 流程
    2. 管理组件生命周期
    3. 统一错误处理
    4. 返回标准化的 UnifiedVerificationResult

    线程安全设计：
    - 单例创建使用独立的锁
    - 组件初始化使用独立的锁
    - 后台知识集成使用独立的锁
    - 所有锁通过LockManager管理，避免死锁
    """
    _instance = None
    _singleton_lock = threading.Lock()  # 单例创建专用锁

    def __new__(cls):
        """实现单例模式，确保全局只有一个引擎实例"""
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super(RumorJudgeEngine, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 初始化锁管理器（如果可用）
        if THREAD_UTILS_AVAILABLE:
            self._lock_mgr = get_lock_manager()
        else:
            logger.warning("线程安全工具不可用，使用基础锁机制")
            self._lock_mgr = None
            self._init_lock = threading.RLock()
            self._integration_lock = threading.RLock()

        # 延迟加载标志
        self._components_initialized = False
        self._kb = None
        self._cache_manager = None
        self._web_search_tool = None
        self._knowledge_integrator = None
        self._hybrid_retriever = None
        self._parser_chain = None

        # [v0.5.0] 初始化协调器占位符
        self._query_processor = None
        self._retrieval_coordinator = None
        self._analysis_coordinator = None
        self._verdict_generator = None

        self._initialized = True
        logger.info("RumorJudgeEngine 单例实例已创建 (组件将延迟初始化)")

    def _lazy_init(self):
        """延迟初始化核心组件，确保在真正需要时才加载资源"""
        if self._components_initialized:
            return

        # 使用细粒度锁避免与其他锁冲突
        if THREAD_UTILS_AVAILABLE:
            lock_ctx = self._lock_mgr.acquire("component_init", timeout=30)
        else:
            lock_ctx = self._init_lock

        with lock_ctx:
            # 双重检查
            if self._components_initialized:
                return

            logger.info("正在执行组件延迟初始化...")
            try:
                self._kb = EvidenceKnowledgeBase()
                self._cache_manager = CacheManager(embeddings=self._kb.embeddings)
                self._web_search_tool = WebSearchTool()
                self._knowledge_integrator = KnowledgeIntegrator()

                # 初始化混合检索器
                self._hybrid_retriever = HybridRetriever(
                    local_kb=self._kb,
                    web_tool=self._web_search_tool
                )

                self._ensure_kb_ready()

                # 初始化解析器链
                try:
                    self._parser_chain = build_parser_chain()
                except Exception as e:
                    logger.error(f"解析器初始化失败: {e}")
                    self._parser_chain = None

                # [v0.5.0] 初始化协调器
                self._init_coordinators()

                self._components_initialized = True
                logger.info("所有核心组件初始化完成")
            except Exception as e:
                logger.error(f"组件延迟初始化过程中出错: {e}")
                raise

    def _init_coordinators(self):
        """初始化协调器（v0.5.0 新增，v0.5.1 增强）"""
        # 导入协调器
        try:
            from src.core.coordinators import (
                QueryProcessor,
                RetrievalCoordinator,
                AnalysisCoordinator,
                VerdictGenerator
            )
            # [v0.5.1] 传递hybrid_retriever给QueryProcessor以支持并行检索
            self._query_processor = QueryProcessor(
                parser_chain=self._parser_chain,
                cache_manager=self._cache_manager,
                hybrid_retriever=self._hybrid_retriever
            )
            self._retrieval_coordinator = RetrievalCoordinator(
                hybrid_retriever=self._hybrid_retriever,
                kb=self._kb
            )
            self._analysis_coordinator = AnalysisCoordinator()
            self._verdict_generator = VerdictGenerator()
            logger.info("协调器初始化成功")
        except ImportError as e:
            logger.warning(f"协调器导入失败: {e}")
            self._query_processor = None
            self._retrieval_coordinator = None
            self._analysis_coordinator = None
            self._verdict_generator = None

    @property
    def is_ready(self) -> bool:
        """检查引擎核心组件是否已就绪"""
        return self._components_initialized

    @property
    def kb(self):
        self._lazy_init()
        return self._kb

    @property
    def cache_manager(self):
        self._lazy_init()
        return self._cache_manager

    @property
    def web_search_tool(self):
        self._lazy_init()
        return self._web_search_tool

    @property
    def knowledge_integrator(self):
        self._lazy_init()
        return self._knowledge_integrator

    @property
    def hybrid_retriever(self):
        self._lazy_init()
        return self._hybrid_retriever

    @property
    def parser_chain(self):
        self._lazy_init()
        return self._parser_chain

    def _ensure_kb_ready(self):
        """确保知识库已就绪，如果未构建则构建"""
        if not self._kb.persist_dir.exists():
            logger.warning(f"向量知识库不存在，正在从 {self._kb.data_dir} 构建...")
            try:
                self._kb.build()
            except Exception as e:
                logger.error(f"知识库构建失败: {e}")

    def _auto_integrate_knowledge(self, result: UnifiedVerificationResult):
        """
        自动知识沉淀：如果通过联网搜索获得了高置信度的结论，将其异步转化为本地知识。

        [2026-02-04 升级] 实施方案 A：提高自动沉淀的准入门槛
        1. 结论必须是绝对定性 ("真" 或 "假")
        2. 置信度 >= config.AUTO_INTEGRATE_MIN_CONFIDENCE
        3. 必须包含至少 config.AUTO_INTEGRATE_MIN_EVIDENCE 条支持/反对的证据

        [v0.3.0 升级] 线程安全改进：
        - 使用上下文管理器自动释放锁
        - 避免手动release导致的锁泄漏
        - 支持超时机制防止死锁
        """
        # 从 config 读取阈值
        min_confidence = getattr(config, 'AUTO_INTEGRATE_MIN_CONFIDENCE', 90)
        min_evidence = getattr(config, 'AUTO_INTEGRATE_MIN_EVIDENCE', 3)

        # 门槛 1 & 2: 结论明确且置信度高
        valid_verdicts = ["真", "假"]
        if result.final_verdict not in valid_verdicts:
            logger.info(f"自动沉淀跳过: 结论 '{result.final_verdict}' 不够明确，仅支持 '真' 或 '假'。")
            return

        if result.confidence_score < min_confidence:
            logger.info(f"自动沉淀跳过: 置信度 {result.confidence_score} 低于阈值 {min_confidence}。")
            return

        # 门槛 3: 证据数量充足
        if len(result.retrieved_evidence) < min_evidence:
            logger.info(f"自动沉淀跳过: 证据数量 {len(result.retrieved_evidence)} 不足 (需 >= {min_evidence})。")
            return

        if result.is_web_search:
            logger.info(f"符合严格自动沉淀条件，尝试启动后台集成线程: {result.query}")

            def background_integration():
                """后台线程执行知识集成"""
                # 使用上下文管理器自动管理锁
                try:
                    # 尝试非阻塞获取锁
                    if THREAD_UTILS_AVAILABLE:
                        # 使用LockManager，超时1秒
                        lock_ctx = self._lock_mgr.acquire("knowledge_integration", timeout=1.0)
                    else:
                        # 回退到传统锁
                        lock_ctx = self._integration_lock
                        if not lock_ctx.acquire(blocking=False):
                            logger.warning("已有知识集成任务在运行中，跳过本次自动沉淀。")
                            return

                    with lock_ctx:
                        logger.info("开始执行后台知识沉淀流程...")
                        # 1. 构造集成内容
                        combined_evidence = "\n\n".join([
                            f"来源: {ev['metadata']['source']}\n内容: {ev['content']}"
                            for ev in result.retrieved_evidence
                        ])

                        content = self.knowledge_integrator.generate_knowledge_content(
                            query=result.query,
                            comment=f"系统自动联网核查结果：\n结论：{result.final_verdict}\n总结：{result.summary_report}\n\n外部参考：\n{combined_evidence}"
                        )

                        if content:
                            timestamp = int(datetime.now().timestamp())
                            safe_title = "".join([c for c in result.query if c.isalnum()])[:20]
                            # [方案 B] 添加元数据标记前缀
                            filename = f"AUTO_GEN_{timestamp}_{safe_title}.txt"
                            file_path = self.knowledge_integrator.rumor_data_dir / filename

                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)

                            logger.info(f"✅ 自动生成知识文件 (带标记): {filename}")

                            # 2. 增量重构向量库
                            logger.info("开始增量更新向量知识库...")
                            self.knowledge_integrator.rebuild_knowledge_base()
                            logger.info("后台知识集成与重构全部完成！")

                except TimeoutError:
                    logger.warning("获取知识集成锁超时，跳过本次自动沉淀")
                except Exception as e:
                    logger.error(f"后台知识集成失败: {e}")
                # 锁会自动释放，无需手动release

            # 启动线程
            thread = threading.Thread(target=background_integration)
            thread.daemon = True
            thread.start()
            logger.info("已将集成任务分发至后台线程。")

    def run(self, query: str, use_cache: bool = True) -> UnifiedVerificationResult:
        """
        执行完整的核查流程

        [v0.5.1] 完全使用协调器模式，移除legacy实现
        [v0.5.2] 添加协调器可用性检查
        """
        start_time = datetime.now()
        logger.info(f"开始核查请求: {query}")

        # 确保组件已初始化
        self._lazy_init()

        # 检查协调器是否可用
        if not self._use_coordinators():
            logger.error("协调器未正确初始化，无法执行核查")
            result = UnifiedVerificationResult(query=query)
            result.final_verdict = "系统错误"
            result.summary_report = "协调器初始化失败，请检查系统配置"
            result.is_fallback = True
            result.add_metadata(PipelineStage.PARSING, False, "协调器未初始化")
            return result

        # [v0.5.1] 使用协调器模式
        return self._run_with_coordinators(query, use_cache, start_time)

    def _use_coordinators(self) -> bool:
        """检查是否使用协调器模式（v0.5.0）"""
        # 检查所有协调器是否已初始化
        return all([
            self._query_processor is not None,
            self._retrieval_coordinator is not None,
            self._analysis_coordinator is not None,
            self._verdict_generator is not None
        ])

    def _run_with_coordinators(
        self,
        query: str,
        use_cache: bool,
        start_time: datetime
    ) -> UnifiedVerificationResult:
        """
        使用协调器模式执行核查（v0.5.1 增强版）

        这个版本使用协调器模式，支持并行解析、解析词补测、去重等完整功能
        [v0.5.2] 添加协调器可用性检查
        """
        result = UnifiedVerificationResult(query=query)

        # [v0.5.2] 二次检查协调器可用性
        if not all([
            self._query_processor is not None,
            self._retrieval_coordinator is not None,
            self._analysis_coordinator is not None,
            self._verdict_generator is not None
        ]):
            logger.error("_run_with_coordinators: 协调器未正确初始化")
            result.final_verdict = "系统错误"
            result.summary_report = "协调器初始化失败"
            result.is_fallback = True
            result.add_metadata(PipelineStage.PARSING, False, "协调器未初始化")
            return result

        # 阶段1: 查询处理（解析 + 缓存检查）
        logger.info("阶段1: 查询处理")

        # [v0.5.1] 使用并行解析和检索
        parsed, local_docs = self._query_processor.parse_with_parallel_retrieval(query)

        if parsed:
            result.entity = parsed.entity
            result.claim = parsed.claim
            result.category = parsed.category
            result.add_metadata(PipelineStage.PARSING, True)

        # 检查缓存（在解析后）
        if use_cache:
            cached = self._query_processor.check_cache(query)
            if cached:
                result.is_cached = True
                result.final_verdict = cached.verdict.value
                result.confidence_score = cached.confidence
                result.risk_level = cached.risk_level
                result.summary_report = cached.summary
                result.add_metadata(
                    PipelineStage.CACHE_CHECK,
                    True,
                    duration=(datetime.now() - start_time).total_seconds() * 1000
                )
                return result
            else:
                result.add_metadata(PipelineStage.CACHE_CHECK, True)
        else:
            result.add_metadata(PipelineStage.CACHE_CHECK, True, "Cache skipped")

        # 阶段2: 证据检索（使用增强的协调器）
        logger.info("阶段2: 证据检索")
        retrieval_start = datetime.now()

        # [v0.7.1] 统一使用 retrieve_with_parsed_query，确保复用已检索的本地文档
        if parsed:
            evidence_list = self._retrieval_coordinator.retrieve_with_parsed_query(
                query=query,
                parsed_info=parsed,
                local_docs=local_docs
            )
        else:
            # [v0.7.1] 即使解析失败，也复用已检索的 local_docs
            # 创建一个空的 parsed_info 对象来复用现有逻辑
            from types import SimpleNamespace
            empty_parsed = SimpleNamespace(entity=None, claim=None, category=None)
            evidence_list = self._retrieval_coordinator.retrieve_with_parsed_query(
                query=query,
                parsed_info=empty_parsed,
                local_docs=local_docs
            )

        # 获取检索统计
        stats = self._retrieval_coordinator.get_retrieval_stats(evidence_list)
        result.retrieved_evidence = evidence_list
        result.is_web_search = stats['is_web_search']

        if result.is_web_search:
            result.add_metadata(
                PipelineStage.WEB_SEARCH,
                True,
                duration=(datetime.now() - retrieval_start).total_seconds() * 1000
            )
        else:
            result.add_metadata(
                PipelineStage.RETRIEVAL,
                True,
                duration=(datetime.now() - retrieval_start).total_seconds() * 1000
            )

        logger.info(f"检索完成: {stats}")

        # 阶段3: 证据分析
        logger.info("阶段3: 证据分析")
        if evidence_list:
            claim = result.claim if result.claim else query
            assessments = self._analysis_coordinator.analyze(
                claim=claim,
                evidence_list=evidence_list
            )
            result.evidence_assessments = assessments

            result.add_metadata(PipelineStage.ANALYSIS, True)
        else:
            logger.warning("无证据，跳过分析")
            result.add_metadata(PipelineStage.ANALYSIS, True, "无证据")

        # 阶段4: 生成裁决
        logger.info("阶段4: 生成裁决")
        verdict_start = datetime.now()

        if evidence_list:
            # 有证据，正常生成裁决
            verdict = self._verdict_generator.generate(
                query=query,
                entity=result.entity,
                claim=result.claim,
                evidence_list=evidence_list,
                assessments=result.evidence_assessments
            )
        else:
            # 无证据，使用兜底机制
            logger.warning("无证据，使用兜底机制")
            from src.analyzers.truth_summarizer import summarize_with_fallback
            full_claim = f"{result.entity} {result.claim}" if result.entity else query
            verdict = summarize_with_fallback(full_claim)
            if verdict:
                result.is_fallback = True

        if verdict:
            result.final_verdict = verdict.verdict.value
            result.confidence_score = verdict.confidence
            result.risk_level = verdict.risk_level
            result.summary_report = verdict.summary

            # 缓存结果
            try:
                self.cache_manager.set_verdict(query, verdict, ttl=self.cache_manager.default_ttl)
                result.saved_to_cache = True
            except Exception as e:
                logger.error(f"缓存保存失败: {e}")

            result.add_metadata(
                PipelineStage.VERDICT,
                True,
                duration=(datetime.now() - verdict_start).total_seconds() * 1000
            )

            # 尝试自动知识集成
            self._auto_integrate_knowledge(result)
        else:
            logger.error("真相总结生成失败：返回结果为空")
            result.add_metadata(PipelineStage.VERDICT, False, "总结生成失败")

        return result

