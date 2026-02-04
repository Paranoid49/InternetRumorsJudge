import gradio as gr
import logging
import json
import requests
import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebInterface")

# API Configuration
API_BASE_URL = os.getenv("RUMOR_API_URL", "http://localhost:8000")
logger.info(f"WebInterface configured to use API: {API_BASE_URL}")

FEEDBACK_FILE = "user_feedback.jsonl"
query_history = []

def verify(query):
    if not query.strip():
        yield ("请输入有效内容", "", "{}", pd.DataFrame(query_history[:20] if query_history else []), query)
        return
    
    logger.info(f"Starting streaming query for: {query}")
    
    # 初始进度提示
    progress_md = f"# ⏳ 正在核查: {query}\n\n"
    yield (progress_md + "> 🚀 启动核查流程...", "", "{}", pd.DataFrame(query_history[:20]), query)

    try:
        # 使用流式 API
        response = requests.post(
            f"{API_BASE_URL}/verify-stream",
            json={"query": query, "use_cache": True, "detailed": True},
            stream=True,
            timeout=120
        )
        
        if response.status_code != 200:
            error_msg = f"API 错误 (HTTP {response.status_code}): {response.text}"
            yield (error_msg, "", "{}", pd.DataFrame(query_history), query)
            return

        final_result = None
        for line in response.iter_lines():
            if not line:
                continue
            
            data = json.loads(line.decode('utf-8'))
            msg_type = data.get("type")
            
            if msg_type == "status":
                stage = data.get("stage")
                if stage == "started":
                    status_text = "正在初始化..."
                elif stage == "processing":
                    status_text = "正在检索证据并进行深度分析..."
                else:
                    status_text = f"正在进行: {stage}"
                
                yield (progress_md + f"> ⚙️ {status_text}", "", "{}", pd.DataFrame(query_history[:20]), query)
                
            elif msg_type == "result":
                final_result = data
                # 1. 完整报告 (Markdown)
                verdict = data.get("verdict", "未定")
                confidence = data.get("confidence", 0)
                summary = data.get("summary", "")
                is_cached = data.get("is_cached", False)
                
                report_md = f"""
# ⚖️ 核查结论: {verdict}
**置信度**: {confidence}/100 

### 📝 总结报告
{summary}
"""
                if is_cached:
                    report_md += "\n\n*(⚡ 结果来自缓存)*"

                # 2. 证据展示 (Markdown)
                evidence_md = "### 🔍 检索到的关键证据\n\n"
                evidence_list = data.get("evidence", [])
                if evidence_list:
                    for i, ev in enumerate(evidence_list, 1):
                        content = ev.get('content', ev.get('text', str(ev)))
                        source = ev.get('metadata', {}).get('source', '未知来源')
                        evidence_md += f"**证据 {i}** (来源: {source}):\n> {content}\n\n---\n"
                else:
                    evidence_md += "_未检索到本地相关证据_"

                # 3. 详情 (JSON)
                details_json = json.dumps(data, indent=2, ensure_ascii=False)

                # 4. 更新历史记录
                history_entry = {
                    "时间": datetime.now().strftime("%H:%M:%S"),
                    "查询内容": query,
                    "结论": verdict,
                    "置信度": confidence,
                    "缓存命中": "✅" if is_cached else "❌"
                }
                query_history.insert(0, history_entry)
                history_df = pd.DataFrame(query_history[:20])

                yield (report_md, evidence_md, details_json, history_df, query)

            elif msg_type == "error":
                error_md = f"❌ 核查出错: {data.get('summary', '未知错误')}"
                yield (error_md, "", json.dumps(data, indent=2, ensure_ascii=False), pd.DataFrame(query_history), query)

    except requests.exceptions.RequestException as e:
        logger.error(f"API Connection Error: {e}")
        error_md = f"❌ 无法连接到 API 服务 ({API_BASE_URL})。请确保 API 服务已启动。"
        yield (error_md, "", "{}", pd.DataFrame(query_history), query)
    except Exception as e:
        logger.error(f"Unexpected Error: {e}")
        error_md = f"❌ 系统发生错误: {str(e)}"
        yield (error_md, "", "{}", pd.DataFrame(query_history), query)

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
    demo.launch(server_name="0.0.0.0", server_port=7860)
