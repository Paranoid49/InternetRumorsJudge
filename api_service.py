import uvicorn
import time
import json
import threading
import queue
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pipeline import RumorJudgeEngine, UnifiedVerificationResult
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("uvicorn.error")

# 初始化 FastAPI 应用
app = FastAPI(
    title="谣言粉碎机 API 服务",
    description="基于 RumorJudgeEngine 的谣言核查 API 接口，提供高性能、自动化的谣言鉴别服务。",
    version="1.1.0"
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
# 并在启动时预加载资源，避免首次请求延迟
engine = RumorJudgeEngine()

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
    
    - **query**: 需要核查的谣言文本
    - **use_cache**: 是否使用缓存 (默认 True)
    - **detailed**: 是否返回详细证据 (默认 False)
    """
    start_time = time.time()
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    
    try:
        logger.info(f"收到核查请求: {request.query} (cache={request.use_cache})")
        # 调用核心引擎
        result = engine.run(request.query, use_cache=request.use_cache)
        
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

    if request.use_cache:
        try:
            cached_verdict = engine.cache_manager.get_verdict(request.query)
            if cached_verdict:
                cached_response = {
                    "type": "result",
                    "success": True,
                    "query": request.query,
                    "verdict": cached_verdict.verdict.value,
                    "confidence": cached_verdict.confidence,
                    "summary": cached_verdict.summary,
                    "is_cached": True,
                    "execution_time_ms": (time.time() - start_time) * 1000
                }

                def cached_gen():
                    yield ndjson_message(cached_response)

                return StreamingResponse(cached_gen(), media_type="application/x-ndjson")
        except Exception as e:
            error_payload = {
                "type": "error",
                "success": False,
                "query": request.query,
                "verdict": "System Error",
                "confidence": 0,
                "summary": str(e),
                "is_cached": False,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            }

            def error_gen():
                yield ndjson_message(error_payload)

            return StreamingResponse(error_gen(), media_type="application/x-ndjson")

    result_queue: queue.Queue = queue.Queue()

    def worker():
        try:
            result = engine.run(request.query, use_cache=False)
            duration = (time.time() - start_time) * 1000
            response = build_verification_response(result, duration, request.detailed).model_dump()
            response["type"] = "result"
            result_queue.put(response)
        except Exception as e:
            result_queue.put({
                "type": "error",
                "success": False,
                "query": request.query,
                "verdict": "System Error",
                "confidence": 0,
                "summary": str(e),
                "is_cached": False,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            })

    threading.Thread(target=worker, daemon=True).start()

    def event_gen():
        yield ndjson_message({"type": "status", "stage": "started", "query": request.query})
        last_ping = time.time()
        while True:
            try:
                payload = result_queue.get(timeout=0.2)
                yield ndjson_message(payload)
                if payload.get("type") in ("result", "error"):
                    break
            except queue.Empty:
                if time.time() - last_ping >= 1.0:
                    yield ndjson_message({"type": "status", "stage": "processing"})
                    last_ping = time.time()

    return StreamingResponse(event_gen(), media_type="application/x-ndjson")

@app.post("/batch-verify", response_model=Dict[str, Any], tags=["Verification"])
async def batch_verify(request: BatchVerifyRequest):
    """
    批量谣言核查接口
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="查询列表不能为空")
        
    results = []
    success_count = 0
    
    for query in request.queries:
        if not query.strip():
            continue
            
        try:
            # 复用 verify 逻辑
            res = engine.run(query, use_cache=request.use_cache)
            results.append({
                "query": query,
                "success": True,
                "verdict": res.final_verdict,
                "confidence": res.confidence_score,
                "summary": res.summary_report
            })
            success_count += 1
        except Exception as e:
            results.append({
                "query": query,
                "success": False,
                "error": str(e)
            })
            
    return {
        "total": len(request.queries),
        "successful": success_count,
        "results": results
    }

if __name__ == "__main__":
    # 生产环境建议使用: uvicorn api_service:app --host 0.0.0.0 --port 8000 --workers 4
    uvicorn.run("api_service:app", host="0.0.0.0", port=8000, reload=True)
