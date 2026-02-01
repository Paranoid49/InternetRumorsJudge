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

    def run(self, query: str, use_cache: bool = True) -> UnifiedVerificationResult:
        """执行完整的核查流程"""
        start_time = datetime.now()
        result = UnifiedVerificationResult(query=query)
        
        # 1. 缓存检查
        if use_cache:
            try:
                cached_verdict = self.cache_manager.get_verdict(query)
                if cached_verdict:
                    result.is_cached = True
                    result.final_verdict = cached_verdict.verdict.value
                    result.confidence_score = cached_verdict.confidence
                    result.risk_level = cached_verdict.risk_level
                    result.summary_report = cached_verdict.summary
                    result.add_metadata(PipelineStage.CACHE_CHECK, True, duration=(datetime.now() - start_time).total_seconds() * 1000)
                    return result
                result.add_metadata(PipelineStage.CACHE_CHECK, True) # Cache miss but success check
            except Exception as e:
                result.add_metadata(PipelineStage.CACHE_CHECK, False, str(e))
        else:
             result.add_metadata(PipelineStage.CACHE_CHECK, True, "Cache skipped by request")

        # 2. 查询解析
        parse_start = datetime.now()
        if not self.parser_chain:
            result.add_metadata(PipelineStage.PARSING, False, "解析器未初始化")
            return result
            
        try:
            analysis: QueryAnalysis = self.parser_chain.invoke({"query": query})
            result.entity = analysis.entity
            result.claim = analysis.claim
            result.category = analysis.category
            result.add_metadata(PipelineStage.PARSING, True, duration=(datetime.now() - parse_start).total_seconds() * 1000)
        except Exception as e:
            result.add_metadata(PipelineStage.PARSING, False, str(e))
            return result

        # 3. 证据检索
        retrieval_start = datetime.now()
        try:
            search_query = f"{result.entity} {result.claim}"
            # 检索 top 3
            evidences = self.kb.search(search_query, k=3)
            result.retrieved_evidence = evidences
            
            if not evidences:
                result.add_metadata(PipelineStage.RETRIEVAL, True, "未找到相关证据", duration=(datetime.now() - retrieval_start).total_seconds() * 1000)
                
                # 进入 fallback 流程
                fallback_start = datetime.now()
                try:
                    logger.info("未找到本地证据，启动 LLM 知识库兜底...")
                    full_claim = f"{result.entity} {result.claim}"
                    fallback_verdict = summarize_with_fallback(full_claim)
                    
                    if fallback_verdict:
                        result.is_fallback = True
                        result.final_verdict = fallback_verdict.verdict.value
                        result.confidence_score = fallback_verdict.confidence
                        result.risk_level = fallback_verdict.risk_level
                        result.summary_report = fallback_verdict.summary
                        
                        # 写入缓存（可选择是否缓存兜底结果，这里选择缓存）
                        self.cache_manager.set_verdict(query, fallback_verdict)
                        result.saved_to_cache = True
                        
                        result.add_metadata(PipelineStage.VERDICT, True, "兜底分析成功", duration=(datetime.now() - fallback_start).total_seconds() * 1000)
                    else:
                        result.final_verdict = "证据不足"
                        result.summary_report = "知识库中未找到证据，且 LLM 无法基于通用知识做出确信判断。"
                        result.add_metadata(PipelineStage.VERDICT, False, "兜底分析失败")
                except Exception as e:
                    result.final_verdict = "证据不足"
                    result.summary_report = f"处理过程出错: {e}"
                    result.add_metadata(PipelineStage.VERDICT, False, f"兜底异常: {e}")

                return result
                
            result.add_metadata(PipelineStage.RETRIEVAL, True, duration=(datetime.now() - retrieval_start).total_seconds() * 1000)
        except Exception as e:
            result.add_metadata(PipelineStage.RETRIEVAL, False, str(e))
            return result

        # 4. 多角度分析
        analysis_start = datetime.now()
        try:
            full_claim = f"{result.entity} {result.claim}"
            assessments = analyze_evidence(full_claim, evidences)
            result.evidence_assessments = assessments
            
            if not assessments:
                result.add_metadata(PipelineStage.ANALYSIS, False, "分析未返回结果")
                return result
                
            result.add_metadata(PipelineStage.ANALYSIS, True, duration=(datetime.now() - analysis_start).total_seconds() * 1000)
        except Exception as e:
            result.add_metadata(PipelineStage.ANALYSIS, False, str(e))
            return result

        # 5. 真相总结
        verdict_start = datetime.now()
        try:
            verdict: FinalVerdict = summarize_truth(full_claim, assessments)
            if verdict:
                result.final_verdict = verdict.verdict.value
                result.confidence_score = verdict.confidence
                result.risk_level = verdict.risk_level
                result.summary_report = verdict.summary
                
                # 写入缓存
                self.cache_manager.set_verdict(query, verdict)
                result.saved_to_cache = True
                
                result.add_metadata(PipelineStage.VERDICT, True, duration=(datetime.now() - verdict_start).total_seconds() * 1000)
            else:
                 result.add_metadata(PipelineStage.VERDICT, False, "总结生成失败")
        except Exception as e:
            result.add_metadata(PipelineStage.VERDICT, False, str(e))

        return result
