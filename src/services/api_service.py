import uvicorn
import time
import json
import asyncio
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 修复控制台中文乱码
try:
    from src.utils import encoding_fix
except ImportError:
    pass

# [v1.2.0] 统一日志配置
from src.observability.logger_config import configure_logging, get_logger
configure_logging()  # 使用环境变量配置

from src.core.pipeline import RumorJudgeEngine, UnifiedVerificationResult
from src import config

logger = get_logger("APIService")

# [v1.1.0] 特性开关：是否使用异步引擎
USE_ASYNC_ENGINE = os.getenv("USE_ASYNC_ENGINE", "false").lower() == "true"

# 初始化 FastAPI 应用
app = FastAPI(
    title="谣言粉碎机 API 服务",
    description="基于 RumorJudgeEngine 的谣言核查 API 接口，提供高性能、自动化的谣言鉴别服务。",
    version="1.2.0"
)

# 配置跨域资源共享 (CORS)
# 允许前端应用（如 Vue/React/小程序）从不同域名/端口访问 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议修改为具体的域名列表
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化核心引擎 (单例模式)
# [v1.1.0] 支持异步引擎切换
if USE_ASYNC_ENGINE:
    try:
        from src.core.async_pipeline import AsyncRumorJudgeEngine
        engine = AsyncRumorJudgeEngine()
        logger.info("✅ 使用异步引擎 (AsyncRumorJudgeEngine)")
    except ImportError as e:
        logger.warning(f"异步引擎导入失败，回退到同步引擎: {e}")
        engine = RumorJudgeEngine()
else:
    engine = RumorJudgeEngine()

# 启动后台自动收集任务 (如果开启)
if getattr(config, "ENABLE_AUTO_COLLECT", False):
    try:
        from scripts.rumor_collector import RumorCollector
        collector = RumorCollector()
        collector.start_background_loop()
    except Exception as e:
        logger.warning(f"自动收集功能启动失败: {e}")

# 初始化线程池，用于运行同步的引擎核查任务
executor = ThreadPoolExecutor(max_workers=10)

async def run_engine_async(query: str, use_cache: bool):
    """
    异步运行引擎核查

    [v1.1.0] 支持：
    - 异步引擎：直接 await engine.run_async()
    - 同步引擎：通过线程池执行
    """
    # 如果使用异步引擎
    if USE_ASYNC_ENGINE and hasattr(engine, 'run_async'):
        return await engine.run_async(query, use_cache)

    # 同步引擎通过线程池执行
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, engine.run, query, use_cache)

# --- 数据模型 ---

class VerifyRequest(BaseModel):
    query: str
    use_cache: Optional[bool] = True
    detailed: Optional[bool] = False  # 默认为 False，只返回核心结论；True 返回完整证据链

class VerificationResponse(BaseModel):
    """
    精简版的验证响应，方便前端直接使用
    """
    success: bool
    query: str
    verdict: str
    confidence: int
    summary: str
    is_cached: bool
    execution_time_ms: float
    # 仅当 detailed=True 时返回
    evidence: Optional[List[Dict[str, Any]]] = None
    assessments: Optional[List[Any]] = None
    error: Optional[str] = None

class BatchVerifyRequest(BaseModel):
    queries: List[str]
    use_cache: Optional[bool] = True

class HealthCheckResponse(BaseModel):
    status: str
    timestamp: float
    service: str

def build_verification_response(result: UnifiedVerificationResult, duration_ms: float, detailed: bool) -> VerificationResponse:
    response = VerificationResponse(
        success=True,
        query=result.query,
        verdict=result.final_verdict or "未定",
        confidence=result.confidence_score,
        summary=result.summary_report or "",
        is_cached=result.is_cached,
        execution_time_ms=duration_ms
    )
    if detailed:
        response.evidence = result.retrieved_evidence
        response.assessments = result.evidence_assessments
    return response

def sse_message(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

def ndjson_message(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str) + "\n"

# --- API 端点 ---

@app.get("/", tags=["General"])
async def root():
    """API 服务根路径信息"""
    return {
        "service": "谣言粉碎机 API",
        "version": "1.1.0",
        "docs_url": "/docs",
        "endpoints": {
            "/verify": "POST - 单条谣言核查",
            "/verify-stream": "POST - 单条谣言核查（JSON 行流式输出）",
            "/batch-verify": "POST - 批量谣言核查",
            "/health": "GET - 服务健康检查"
        }
    }

@app.get("/health", response_model=HealthCheckResponse, tags=["General"])
async def health_check():
    """服务健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "RumorJudgeAPI"
    }

@app.post("/verify", response_model=VerificationResponse, tags=["Verification"])
async def verify_rumor(request: VerifyRequest):
    """
    单条谣言核查接口
    """
    start_time = time.time()
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    
    try:
        logger.info(f"收到核查请求: {request.query} (cache={request.use_cache})")
        # 异步调用核心引擎
        result = await run_engine_async(request.query, request.use_cache)
        
        # 计算总耗时
        duration = (time.time() - start_time) * 1000
        
        response = build_verification_response(result, duration, request.detailed)
        return response
        
    except Exception as e:
        logger.error(f"请求处理出错: {e}")
        # 优雅降级：返回错误状态而不是 HTTP 500，方便前端处理业务逻辑
        return VerificationResponse(
            success=False,
            query=request.query,
            verdict="System Error",
            confidence=0,
            summary=str(e),
            is_cached=False,
            execution_time_ms=(time.time() - start_time) * 1000,
            error=str(e)
        )

@app.post("/verify-stream", tags=["Verification"])
async def verify_stream(request: VerifyRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")

    start_time = time.time()

    async def event_gen():
        yield ndjson_message({"type": "status", "stage": "started", "query": request.query})
        
        try:
            # 1. 尝试获取缓存（非阻塞）
            if request.use_cache:
                loop = asyncio.get_event_loop()
                cached_verdict = await loop.run_in_executor(executor, engine.cache_manager.get_verdict, request.query)
                if cached_verdict:
                    yield ndjson_message({
                        "type": "result",
                        "success": True,
                        "query": request.query,
                        "verdict": cached_verdict.verdict.value,
                        "confidence": cached_verdict.confidence,
                        "summary": cached_verdict.summary,
                        "is_cached": True,
                        "execution_time_ms": (time.time() - start_time) * 1000
                    })
                    return

            # 2. 运行完整流程（异步）
            yield ndjson_message({"type": "status", "stage": "processing"})
            result = await run_engine_async(request.query, request.use_cache)
            duration = (time.time() - start_time) * 1000
            
            response = build_verification_response(result, duration, request.detailed).model_dump()
            response["type"] = "result"
            yield ndjson_message(response)
            
        except Exception as e:
            logger.error(f"流式核查出错: {e}")
            yield ndjson_message({
                "type": "error",
                "success": False,
                "query": request.query,
                "verdict": "System Error",
                "is_cached": False,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            })

    return StreamingResponse(event_gen(), media_type="application/x-ndjson")


@app.post("/verify-stream-enhanced", tags=["Verification"])
async def verify_stream_enhanced(request: VerifyRequest):
    """
    增强版流式响应（优化方案2）

    提供更细粒度的进度反馈，改善用户体验
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")

    start_time = time.time()

    async def event_gen_enhanced():
        # 阶段1: 开始
        yield ndjson_message({
            "type": "status",
            "stage": "started",
            "query": request.query,
            "timestamp": time.time()
        })

        try:
            # 1.1 缓存检查（快速返回）
            if request.use_cache:
                yield ndjson_message({"type": "status", "stage": "cache_check", "status": "checking"})
                loop = asyncio.get_event_loop()
                cached_verdict = await loop.run_in_executor(
                    executor,
                    engine.cache_manager.get_verdict,
                    request.query
                )
                if cached_verdict:
                    duration = (time.time() - start_time) * 1000
                    yield ndjson_message({
                        "type": "result",
                        "success": True,
                        "query": request.query,
                        "verdict": cached_verdict.verdict.value,
                        "confidence": cached_verdict.confidence,
                        "summary": cached_verdict.summary,
                        "is_cached": True,
                        "execution_time_ms": duration
                    })
                    return
                else:
                    yield ndjson_message({"type": "status", "stage": "cache_check", "status": "miss"})

            # 阶段2: 查询解析（~1-2秒后返回）
            yield ndjson_message({"type": "status", "stage": "parsing", "status": "started"})

            # 运行完整流程但不使用stream（因为我们想分阶段报告）
            result = await run_engine_async(request.query, False)  # 禁用缓存，自己控制

            # 报告解析完成
            if result.entity or result.claim:
                yield ndjson_message({
                    "type": "progress",
                    "stage": "parsing",
                    "status": "completed",
                    "entity": result.entity,
                    "claim": result.claim,
                    "category": result.category,
                    "elapsed_ms": (time.time() - start_time) * 1000
                })

            # 阶段3: 检索完成（~2-4秒后返回）
            if result.retrieved_evidence:
                yield ndjson_message({
                    "type": "progress",
                    "stage": "retrieval",
                    "status": "completed",
                    "evidence_count": len(result.retrieved_evidence),
                    "is_web_search": result.is_web_search,
                    "elapsed_ms": (time.time() - start_time) * 1000
                })

            # 阶段4: 证据分析进度
            if result.evidence_assessments:
                total = len(result.evidence_assessments)
                for i, assessment in enumerate(result.evidence_assessments):
                    yield ndjson_message({
                        "type": "progress",
                        "stage": "analysis",
                        "status": "in_progress",
                        "current": i + 1,
                        "total": total,
                        "evidence_id": assessment.id,
                        "relevance": assessment.relevance,
                        "stance": assessment.stance,
                        "elapsed_ms": (time.time() - start_time) * 1000
                    })

                yield ndjson_message({
                    "type": "progress",
                    "stage": "analysis",
                    "status": "completed",
                    "total": total,
                    "elapsed_ms": (time.time() - start_time) * 1000
                })

            # 阶段5: 最终结果
            duration = (time.time() - start_time) * 1000
            response = build_verification_response(result, duration, request.detailed).model_dump()
            response["type"] = "result"
            response["elapsed_ms"] = duration
            yield ndjson_message(response)

        except Exception as e:
            logger.error(f"增强流式核查出错: {e}")
            yield ndjson_message({
                "type": "error",
                "success": False,
                "query": request.query,
                "verdict": "System Error",
                "is_cached": False,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            })

    return StreamingResponse(event_gen_enhanced(), media_type="application/x-ndjson")

@app.post("/batch-verify", response_model=Dict[str, Any], tags=["Verification"])
async def batch_verify(request: BatchVerifyRequest):
    """
    批量谣言核查接口（并发执行）
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="查询列表不能为空")
    
    queries = [q.strip() for q in request.queries if q.strip()]
    
    async def single_verify(query: str):
        try:
            res = await run_engine_async(query, request.use_cache)
            return {
                "query": query,
                "success": True,
                "verdict": res.final_verdict,
                "confidence": res.confidence_score,
                "summary": res.summary_report
            }
        except Exception as e:
            return {
                "query": query,
                "success": False,
                "error": str(e)
            }

    # 并发执行所有查询
    results = await asyncio.gather(*(single_verify(q) for q in queries))
    
    success_count = sum(1 for r in results if r["success"])
            
    return {
        "total": len(queries),
        "successful": success_count,
        "results": results
    }

# --- 监控端点 (v1.1.0 新增) ---

@app.get("/monitor/stats", tags=["Monitoring"])
async def get_monitoring_stats():
    """
    获取 API 监控统计数据

    返回今日和本月的 API 使用统计。
    """
    try:
        from src.observability.api_monitor import get_api_monitor
        monitor = get_api_monitor()

        daily = monitor.get_daily_summary()
        monthly = monitor.get_monthly_summary()
        alerts = monitor.get_recent_alerts(10)

        return {
            "success": True,
            "daily": daily,
            "monthly": monthly,
            "recent_alerts": alerts
        }
    except Exception as e:
        logger.error(f"获取监控统计失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/monitor/report", tags=["Monitoring"])
async def get_monitoring_report(days: int = Query(default=7, ge=1, le=30)):
    """
    生成 API 监控报告

    Args:
        days: 报告天数（1-30天）

    Returns:
        文本格式的监控报告
    """
    try:
        from src.observability.api_monitor import get_api_monitor
        monitor = get_api_monitor()
        report = monitor.generate_report(days=days)

        return {
            "success": True,
            "days": days,
            "report": report
        }
    except Exception as e:
        logger.error(f"生成监控报告失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/monitor/health", tags=["Monitoring"])
async def get_monitoring_health():
    """
    获取 API 健康状态

    返回系统各组件的健康状态和最近的告警。
    """
    try:
        from src.observability.api_monitor import get_api_monitor
        monitor = get_api_monitor()

        # 获取今日统计
        daily = monitor.get_daily_summary()

        # 计算健康状态
        health_status = "healthy"
        warnings = []

        # 检查是否有超支告警
        alerts = monitor.get_recent_alerts(5)
        critical_alerts = [a for a in alerts if a.get('level') == 'critical']

        if critical_alerts:
            health_status = "warning"
            warnings.extend([a['message'] for a in critical_alerts])

        return {
            "success": True,
            "status": health_status,
            "timestamp": time.time(),
            "daily_usage": {
                "cost": daily.get('total_cost', 0),
                "tokens": daily.get('total_tokens', 0),
                "calls": daily.get('api_calls', 0)
            },
            "warnings": warnings,
            "recent_alerts": alerts
        }
    except Exception as e:
        logger.error(f"获取健康状态失败: {e}")
        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    # 生产环境建议使用: uvicorn api_service:app --host 0.0.0.0 --port 8000 --workers 4
    uvicorn.run("api_service:app", host="0.0.0.0", port=8000, reload=True)
