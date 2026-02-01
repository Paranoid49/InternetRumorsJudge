from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
from your_main_module import EnhancedRumorVerificationSystem

# 初始化FastAPI应用和系统
app = FastAPI(
    title="谣言鉴定助手API",
    description="基于AI的自动化谣言事实核查服务",
    version="1.0.0"
)

# 允许跨域请求（如果前端在不同端口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化系统
system = EnhancedRumorVerificationSystem()


# 定义数据模型
class VerificationRequest(BaseModel):
    text: str
    use_cache: Optional[bool] = True
    detailed: Optional[bool] = False  # 是否返回详细证据


class VerificationResponse(BaseModel):
    success: bool
    query: str
    conclusion: str
    confidence: Optional[float] = None
    entities: Optional[List[str]] = None
    top_evidence: Optional[List[str]] = None
    processing_time_ms: Optional[int] = None
    from_cache: Optional[bool] = False
    error_message: Optional[str] = None


# 根端点
@app.get("/")
async def root():
    return {
        "service": "谣言鉴定助手API",
        "version": "1.0.0",
        "endpoints": {
            "/verify": "POST - 验证谣言",
            "/health": "GET - 服务健康检查",
            "/history": "GET - 查询历史（如果实现）"
        }
    }


# 健康检查端点
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z"  # 实际使用datetime.now().isoformat()
    }


# 核心验证端点
@app.post("/verify", response_model=VerificationResponse)
async def verify_rumor(request: VerificationRequest):
    """验证谣言的核心端点"""
    import time
    start_time = time.time()

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="输入文本不能为空")

    try:
        # 调用系统
        if request.use_cache:
            result = system.verify_with_cache(request.text)
        else:
            result = system.verify(request.text)

        # 构建响应
        response_data = {
            "success": True,
            "query": request.text,
            "conclusion": result.get("final_report", "未生成结论"),
            "from_cache": result.get("_from_cache", False),
            "processing_time_ms": int((time.time() - start_time) * 1000)
        }

        # 如果请求详细结果
        if request.detailed:
            parsed = result.get("parsed_query", {})
            response_data["entities"] = [parsed.get("entity", "")]
            evidence_list = result.get("evidence", [])
            response_data["top_evidence"] = [e.get("content", "")[:200] for e in evidence_list[:3]]

        return VerificationResponse(**response_data)

    except Exception as e:
        return VerificationResponse(
            success=False,
            query=request.text,
            conclusion="",
            error_message=f"处理失败: {str(e)}",
            processing_time_ms=int((time.time() - start_time) * 1000)
        )


# 批量验证端点（可选）
@app.post("/batch-verify")
async def batch_verify(texts: List[str] = Query(...)):
    """批量验证多个谣言"""
    results = []
    for text in texts:
        try:
            result = system.verify_with_cache(text)
            results.append({
                "text": text,
                "conclusion": result.get("final_report", "无结论")[:100],
                "success": True
            })
        except Exception as e:
            results.append({
                "text": text,
                "conclusion": "",
                "success": False,
                "error": str(e)
            })

    return {
        "total": len(texts),
        "successful": sum(1 for r in results if r["success"]),
        "results": results
    }


if __name__ == "__main__":
    uvicorn.run(
        "api_service:app",
        host="127.0.0.1",
        port=8000,
        reload=True  # 开发模式下自动重载
    )