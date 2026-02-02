import logging
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

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
    import config
    from query_parser import build_chain as build_parser_chain
    from query_parser import QueryAnalysis
    from evidence_retriever import EvidenceKnowledgeBase
    from evidence_analyzer import analyze_evidence, EvidenceAssessment
    from truth_summarizer import summarize_truth, FinalVerdict, VerdictType, summarize_with_fallback
    from cache_manager import CacheManager
    from web_search_tool import WebSearchTool
    from knowledge_integrator import KnowledgeIntegrator
    from hybrid_retriever import HybridRetriever
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
    
    def __init__(self):
        self.kb = EvidenceKnowledgeBase()
        self.cache_manager = CacheManager()
        self.web_search_tool = WebSearchTool()
        self.knowledge_integrator = KnowledgeIntegrator()
        
        # 初始化混合检索器
        self.hybrid_retriever = HybridRetriever(
            local_kb=self.kb, 
            web_tool=self.web_search_tool
        )
        
        self._ensure_kb_ready()
        
        # 初始化解析器链
        try:
            self.parser_chain = build_parser_chain()
        except Exception as e:
            logger.error(f"解析器初始化失败: {e}")
            self.parser_chain = None

    def _ensure_kb_ready(self):
        """确保知识库已就绪，如果未构建则构建"""
        if not self.kb.persist_dir.exists():
            logger.warning(f"向量知识库不存在，正在从 {self.kb.data_dir} 构建...")
            try:
                self.kb.build()
            except Exception as e:
                logger.error(f"知识库构建失败: {e}")

    def _auto_integrate_knowledge(self, result: UnifiedVerificationResult):
        """
        自动知识沉淀：如果通过联网搜索获得了高置信度的结论，将其转化为本地知识。
        """
        if result.is_web_search and result.confidence_score >= 85:
            logger.info(f"触发自动知识沉淀: {result.query} (置信度: {result.confidence_score})")
            try:
                # 构造集成所需的内容
                # 联网结果可能包含多个来源，我们将它们合并作为“证据”传给生成器
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
                    filename = f"AUTO_{timestamp}_{safe_title}.txt"
                    file_path = self.knowledge_integrator.rumor_data_dir / filename
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    logger.info(f"✅ 自动生成知识文件: {filename}")
                    # 重新构建向量库（这里可以考虑是否要立即构建，为了体验先立即构建）
                    self.knowledge_integrator.rebuild_knowledge_base()
            except Exception as e:
                logger.error(f"自动知识沉淀失败: {e}")

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

        # 2. 查询解析
        parse_start = datetime.now()
        logger.info("正在解析查询内容...")
        if not self.parser_chain:
            logger.error("解析器未初始化！")
            result.add_metadata(PipelineStage.PARSING, False, "解析器未初始化")
            return result
            
        try:
            analysis: QueryAnalysis = self.parser_chain.invoke({"query": query})
            result.entity = analysis.entity
            result.claim = analysis.claim
            result.category = analysis.category
            logger.info(f"解析完成: 实体='{result.entity}', 主张='{result.claim}', 分类='{result.category}'")
            result.add_metadata(PipelineStage.PARSING, True, duration=(datetime.now() - parse_start).total_seconds() * 1000)
        except Exception as e:
            logger.error(f"查询解析失败: {e}")
            result.add_metadata(PipelineStage.PARSING, False, str(e))
            return result

        # 3. 混合证据检索
        retrieval_start = datetime.now()
        logger.info("进入混合证据检索阶段...")
        try:
            # 构造多重检索词：解析后的 实体+主张 以及 原始查询，以提高 text-embedding-v4 的匹配率
            parsed_query = f"{result.entity} {result.claim}" if result.entity and result.claim else ""
            search_query = parsed_query if parsed_query else query
            
            # 使用混合检索器
            documents = self.hybrid_retriever.invoke(search_query)
            
            # 如果本地解析词检索效果不佳，且原始查询不同，尝试用原始查询补测一次
            if not any(doc.metadata.get('type') == 'local' for doc in documents) and parsed_query and parsed_query != query:
                logger.info("解析词检索未命中本地库，尝试使用原始查询词补测...")
                extra_docs = self.hybrid_retriever.invoke(query)
                # 合并并去重
                documents = self.hybrid_retriever._deduplicate_docs(documents + extra_docs)
            
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
