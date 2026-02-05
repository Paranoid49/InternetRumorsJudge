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

# 修复控制台中文乱码
try:
    from src.utils import encoding_fix
except ImportError:
    pass

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 配置结构化日志
try:
    from src.observability import configure_logging
    configure_logging(log_level="INFO", json_output=False)  # 开发环境使用可读格式
except ImportError:
    pass  # 回退到标准 logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RumorJudgeEngine")

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
try:
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

    # 导入可观测性模块（可选）
    try:
        from src.observability import get_logger, get_metrics_collector, RequestContext, StageTimer
        OBSERVABILITY_AVAILABLE = True
    except ImportError:
        OBSERVABILITY_AVAILABLE = False
except ImportError as e:
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
except ImportError as e:
    logger.error(f"组件导入失败: {e}")
    raise

class RumorJudgeEngine:
    """
    谣言核查核心引擎
    
    职责:
    1. 编排 pipeline 流程
    2. 管理组件生命周期
    3. 统一错误处理
    4. 返回标准化的 UnifiedVerificationResult
    """
    _instance = None
    _lock = threading.Lock()
    _integration_lock = threading.Lock() # 新增：用于后台知识集成的线程锁

    def __new__(cls):
        """实现单例模式，确保全局只有一个引擎实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RumorJudgeEngine, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        # 延迟加载标志
        self._components_initialized = False
        self._kb = None
        self._cache_manager = None
        self._web_search_tool = None
        self._knowledge_integrator = None
        self._hybrid_retriever = None
        self._parser_chain = None
        
        self._initialized = True
        logger.info("RumorJudgeEngine 单例实例已创建 (组件将延迟初始化)")

    def _lazy_init(self):
        """延迟初始化核心组件，确保在真正需要时才加载资源"""
        if self._components_initialized:
            return
            
        with self._lock:
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
                
                self._components_initialized = True
                logger.info("所有核心组件初始化完成")
            except Exception as e:
                logger.error(f"组件延迟初始化过程中出错: {e}")
                raise

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
                # 使用非阻塞方式获取锁，如果已经有集成任务在跑，则放弃本次任务以节省资源
                if not self._integration_lock.acquire(blocking=False):
                    logger.warning("已有知识集成任务在运行中，跳过本次自动沉淀。")
                    return
                
                try:
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
                except Exception as e:
                    logger.error(f"后台知识集成失败: {e}")
                finally:
                    # 无论成功失败，最后都要释放锁
                    self._integration_lock.release()

            # 启动线程
            thread = threading.Thread(target=background_integration)
            thread.daemon = True
            thread.start()
            logger.info("已将集成任务分发至后台线程。")

    def run(self, query: str, use_cache: bool = True) -> UnifiedVerificationResult:
        """执行完整的核查流程"""
        start_time = datetime.now()
        logger.info(f"开始核查请求: {query}")
        result = UnifiedVerificationResult(query=query)
        
        # 1. 缓存检查
        if use_cache:
            try:
                cached_verdict = self.cache_manager.get_verdict(query)
                if cached_verdict:
                    logger.info("命中缓存，返回预存结果。")
                    result.is_cached = True
                    result.final_verdict = cached_verdict.verdict.value
                    result.confidence_score = cached_verdict.confidence
                    result.risk_level = cached_verdict.risk_level
                    result.summary_report = cached_verdict.summary
                    result.add_metadata(PipelineStage.CACHE_CHECK, True, duration=(datetime.now() - start_time).total_seconds() * 1000)
                    return result
                logger.info("未命中缓存，进入实时核查。")
                result.add_metadata(PipelineStage.CACHE_CHECK, True) # Cache miss but success check
            except Exception as e:
                logger.error(f"缓存检查失败: {e}")
                result.add_metadata(PipelineStage.CACHE_CHECK, False, str(e))
        else:
             logger.info("跳过缓存检查。")
             result.add_metadata(PipelineStage.CACHE_CHECK, True, "Cache skipped by request")

        # 2. 查询解析与本地初步检索并行执行
        parse_start = datetime.now()
        logger.info("正在执行查询解析与本地检索并行化...")
        
        if not self.parser_chain:
            logger.error("解析器未初始化！")
            result.add_metadata(PipelineStage.PARSING, False, "解析器未初始化")
            return result
            
        try:
            # 使用线程池并行执行：解析意图 VS 原始词本地检索
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 任务 1: LLM 解析意图
                parse_future = executor.submit(self.parser_chain.invoke, {"query": query})
                # 任务 2: 原始词直接去本地库查一把（抢跑）
                raw_search_future = executor.submit(self.hybrid_retriever.search_local, query)
                
                # 等待解析完成
                analysis: QueryAnalysis = parse_future.result()
                result.entity = analysis.entity
                result.claim = analysis.claim
                result.category = analysis.category
                logger.info(f"意图解析完成: 实体='{result.entity}', 主张='{result.claim}'")
                result.add_metadata(PipelineStage.PARSING, True, duration=(datetime.now() - parse_start).total_seconds() * 1000)
                
                # 获取抢跑检索结果
                local_docs = raw_search_future.result()
                if local_docs:
                    logger.info(f"原始词抢跑检索命中 {len(local_docs)} 条证据")
            
            # 3. 混合证据检索 (基于已有的解析结果进行补测)
            retrieval_start = datetime.now()
            
            # 如果解析词和原始词不同，用解析词补测本地库
            parsed_query = f"{result.entity} {result.claim}" if result.entity and result.claim else ""
            if parsed_query and parsed_query != query:
                logger.info(f"尝试解析词补测本地检索: '{parsed_query}'")
                local_docs.extend(self.hybrid_retriever.search_local(parsed_query))
            
            # 汇总本地结果并去重
            unique_local_docs = self.hybrid_retriever._deduplicate_docs(local_docs)
            
            # 调用混合检索（传入已有的本地文档，决定是否触发联网）
            search_query = parsed_query if parsed_query else query
            documents = self.hybrid_retriever.search_hybrid(search_query, existing_local_docs=unique_local_docs)
            
            # 更新结果元数据
            result.is_web_search = any(doc.metadata.get('type') == 'web' for doc in documents)
            local_count = sum(1 for doc in documents if doc.metadata.get('type') == 'local')
            web_count = sum(1 for doc in documents if doc.metadata.get('type') == 'web')
            
            logger.info(f"检索完成: 共找到 {len(documents)} 条证据 (本地: {local_count}, 联网: {web_count})")
            
            # 转换为兼容格式 List[Dict] 以供后续分析使用
            evidences = []
            for doc in documents:
                evidences.append({
                    "content": doc.page_content,
                    "text": doc.page_content, # 兼容 evidence_analyzer
                    "metadata": {
                        "source": doc.metadata.get('source', '未知'),
                        "type": doc.metadata.get('type', 'local'),
                        "similarity": doc.metadata.get('similarity', 0.0),
                        "score": doc.metadata.get('score', 0.0)
                    },
                    "source": doc.metadata.get('source', '未知') # 兼容旧版
                })
            
            result.retrieved_evidence = evidences
            
            if result.is_web_search:
                result.add_metadata(PipelineStage.WEB_SEARCH, True, duration=(datetime.now() - retrieval_start).total_seconds() * 1000)
            else:
                result.add_metadata(PipelineStage.RETRIEVAL, True, duration=(datetime.now() - retrieval_start).total_seconds() * 1000)

            # 4. 如果最终还是没证据，走兜底
            if not evidences:
                fallback_start = datetime.now()
                try:
                    logger.warning("未找到任何外部证据，启动 LLM 知识库兜底...")
                    full_claim = f"{result.entity} {result.claim}"
                    fallback_verdict = summarize_with_fallback(full_claim)
                    
                    if fallback_verdict:
                        logger.info(f"兜底核查完成: 结论={fallback_verdict.verdict.value}")
                        result.is_fallback = True
                        result.final_verdict = fallback_verdict.verdict.value
                        result.confidence_score = fallback_verdict.confidence
                        result.risk_level = fallback_verdict.risk_level
                        result.summary_report = fallback_verdict.summary
                        
                        self.cache_manager.set_verdict(query, fallback_verdict)
                        result.saved_to_cache = True
                        result.add_metadata(PipelineStage.VERDICT, True, "兜底分析成功", duration=(datetime.now() - fallback_start).total_seconds() * 1000)
                    else:
                        logger.error("兜底核查失败：LLM 未返回结果")
                        result.final_verdict = "证据不足"
                        result.summary_report = "本地和联网均未找到证据，且 LLM 无法做出确信判断。"
                        result.add_metadata(PipelineStage.VERDICT, False, "兜底分析失败")
                except Exception as e:
                    logger.error(f"兜底核查异常: {e}")
                    result.final_verdict = "证据不足"
                    result.summary_report = f"处理过程出错: {e}"
                    result.add_metadata(PipelineStage.VERDICT, False, f"兜底异常: {e}")

                return result
        except Exception as e:
            logger.error(f"检索阶段出错: {e}")
            result.add_metadata(PipelineStage.RETRIEVAL, False, str(e))
            return result

        # 5. 多角度分析
        analysis_start = datetime.now()
        logger.info(f"开始对 {len(evidences)} 条证据进行多角度分析...")
        try:
            full_claim = f"{result.entity} {result.claim}"
            assessments = analyze_evidence(full_claim, evidences)
            result.evidence_assessments = assessments
            
            if not assessments:
                logger.error("多角度分析未返回任何评估结果")
                result.add_metadata(PipelineStage.ANALYSIS, False, "分析未返回结果")
                return result
                
            logger.info("证据分析完成。")
            result.add_metadata(PipelineStage.ANALYSIS, True, duration=(datetime.now() - analysis_start).total_seconds() * 1000)
        except Exception as e:
            logger.error(f"证据分析阶段出错: {e}")
            result.add_metadata(PipelineStage.ANALYSIS, False, str(e))
            return result

        # 6. 真相总结
        verdict_start = datetime.now()
        logger.info("正在生成最终核查报告...")
        try:
            verdict: FinalVerdict = summarize_truth(full_claim, assessments)
            if verdict:
                result.final_verdict = verdict.verdict.value
                result.confidence_score = verdict.confidence
                result.risk_level = verdict.risk_level
                result.summary_report = verdict.summary
                logger.info(f"核查总结完成: 结论='{result.final_verdict}', 置信度={result.confidence_score}")
                
                # 写入缓存
                self.cache_manager.set_verdict(query, verdict)
                result.saved_to_cache = True
                
                result.add_metadata(PipelineStage.VERDICT, True, duration=(datetime.now() - verdict_start).total_seconds() * 1000)
                
                # 尝试自动知识集成
                self._auto_integrate_knowledge(result)
            else:
                 logger.error("真相总结生成失败：返回结果为空")
                 result.add_metadata(PipelineStage.VERDICT, False, "总结生成失败")
        except Exception as e:
            logger.error(f"真相总结阶段出错: {e}")
            result.add_metadata(PipelineStage.VERDICT, False, str(e))

        logger.info(f"整个核查流程结束，耗时: {(datetime.now() - start_time).total_seconds():.2f}s")
        return result
