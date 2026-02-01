import gradio as gr
from pipeline import RumorJudgeEngine, UnifiedVerificationResult
import logging
import json
from datetime import datetime
import pandas as pd
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebInterface")

# Initialize Engine
try:
    engine = RumorJudgeEngine()
    logger.info("RumorJudgeEngine initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize RumorJudgeEngine: {e}")
    raise

FEEDBACK_FILE = "user_feedback.jsonl"
query_history = []

def verify(query):
    if not query.strip():
        # 返回空状态
        return (
            "请输入有效内容", 
            "", 
            "{}", 
            pd.DataFrame(query_history[-10:]),
            query
        )
    
    logger.info(f"Received query: {query}")
    try:
        result = engine.run(query)
        
        # 1. 完整报告 (Markdown)
        report_md = f"""
# ⚖️ 核查结论: {result.final_verdict}
**置信度**: {result.confidence_score}/100  |  **风险等级**: {result.risk_level}

### 📝 总结报告
{result.summary_report}
"""
        if result.is_fallback:
            report_md = "### ⚠️ 警告: 未找到本地证据，结果基于通用知识，仅供参考。\n\n" + report_md
            
        if result.is_cached:
            report_md += "\n\n*(⚡ 结果来自缓存)*"

        # 2. 证据展示 (Markdown)
        evidence_md = "### 🔍 检索到的关键证据\n\n"
        if result.retrieved_evidence:
            for i, ev in enumerate(result.retrieved_evidence, 1):
                # 尝试获取内容，处理不同格式
                content = ev.get('content', ev.get('text', str(ev)))
                source = ev.get('metadata', {}).get('source', '未知来源')
                evidence_md += f"**证据 {i}** (来源: {source}):\n> {content}\n\n---\n"
        else:
            evidence_md += "_未检索到本地相关证据_"

        # 3. 详情 (JSON)
        assessments_dump = []
        if result.evidence_assessments:
            for a in result.evidence_assessments:
                if hasattr(a, 'model_dump'):
                    assessments_dump.append(a.model_dump())
                else:
                    assessments_dump.append(str(a))
        
        details = {
            "entity": result.entity,
            "claim": result.claim,
            "evidence_count": len(result.retrieved_evidence),
            "retrieved_evidence": result.retrieved_evidence,
            "assessments": assessments_dump,
            "pipeline_metadata": [m.model_dump() for m in result.metadata]
        }
        details_json = json.dumps(details, indent=2, ensure_ascii=False, default=str)

        # 4. 更新历史记录
        history_entry = {
            "时间": datetime.now().strftime("%H:%M:%S"),
            "查询内容": query,
            "结论": result.final_verdict,
            "置信度": result.confidence_score,
            "缓存命中": "✅" if result.is_cached else "❌"
        }
        query_history.insert(0, history_entry) # 最新在最前
        history_df = pd.DataFrame(query_history[:20]) # 只显示最近20条

        return report_md, evidence_md, details_json, history_df, query

    except Exception as e:
        logger.error(f"Error during verification: {e}")
        error_md = f"❌ 系统发生错误: {str(e)}"
        return error_md, error_md, "{}", pd.DataFrame(query_history), query

def save_feedback(query, rating, comment):
    logger.info(f"Attempting to save feedback for query: {query}, rating: {rating}")
    if not query:
        return "请先进行查询后再提交反馈。"
        
    feedback_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "rating": rating,
        "comment": comment
    }
    
    try:
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
        logger.info(f"Feedback saved for query: {query}")
        return "✅ 反馈已提交，感谢您的帮助！"
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        return f"❌ 提交失败: {str(e)}"

# Define custom CSS for a better look
custom_css = """
.gradio-container {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}
"""

with gr.Blocks(title="谣言粉碎机 Pro", theme=gr.themes.Soft(), css=custom_css) as demo:
    gr.Markdown("# 🤖 谣言粉碎机 Pro \n 智能事实核查系统 powered by LLM & RAG")
    
    with gr.Row():
        with gr.Column(scale=4):
            input_text = gr.Textbox(placeholder="输入传言，例如：吃洋葱能治感冒...", label="待核查内容", lines=2)
        with gr.Column(scale=1):
            verify_btn = gr.Button("🔍 开始核查", variant="primary", scale=2)
    
    # 结果展示区 (Tabs)
    with gr.Tabs():
        with gr.TabItem("📝 核查报告"):
            report_output = gr.Markdown()
        
        with gr.TabItem("🔍 证据详情"):
            evidence_output = gr.Markdown()
            
        with gr.TabItem("� 技术解析"):
            json_output = gr.JSON(label="Pipeline 详情")
            
        with gr.TabItem("🕒 查询历史"):
            history_output = gr.Dataframe(
                headers=["时间", "查询内容", "结论", "置信度", "缓存命中"],
                interactive=False
            )

    # Hidden state to store current query for feedback context
    current_query = gr.State()
    
    gr.Markdown("---")
    gr.Markdown("### 🗳️ 结果反馈")
    
    with gr.Row():
        with gr.Column(scale=3):
            feedback_rating = gr.Radio(["有用", "一般", "无用/错误"], label="评价", value="有用")
            feedback_text = gr.Textbox(placeholder="如果不准确，请告诉我们要改进的地方...", label="具体意见")
            feedback_btn = gr.Button("提交反馈")
            feedback_status = gr.Label(visible=True, label="状态", value="")

    # 示例区
    gr.Markdown("### 💡 试试这些例子")
    gr.Examples(
        examples=[
            ["吃洋葱可以预防感冒"],
            ["5G基站辐射会损害人体健康"],
            ["经常喝咖啡会导致骨质疏松"],
            ["微波炉加热食物会产生致癌物质"],
            ["根据最新研究，地球是平的"]
        ],
        inputs=[input_text],
        outputs=[report_output, evidence_output, json_output, history_output, current_query],
        fn=verify,
        cache_examples=False, # 设为False以避免启动时预计算
        run_on_click=True
    )

    # Event handlers
    verify_btn.click(
        fn=verify,
        inputs=[input_text],
        outputs=[report_output, evidence_output, json_output, history_output, current_query]
    )
    
    input_text.submit(
        fn=verify,
        inputs=[input_text],
        outputs=[report_output, evidence_output, json_output, history_output, current_query]
    )
    
    feedback_btn.click(
        fn=save_feedback,
        inputs=[current_query, feedback_rating, feedback_text],
        outputs=[feedback_status]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7861)
