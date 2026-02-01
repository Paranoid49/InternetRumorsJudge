import gradio as gr
import pandas as pd
from datetime import datetime
from your_main_module import EnhancedRumorVerificationSystem  # 导入你强化后的系统

# 初始化系统
system = EnhancedRumorVerificationSystem()
# 用于存储查询历史
query_history = []


def verify_rumor(rumor_text, use_cache=True):
    """核查谣言的核心函数，供界面调用"""
    if not rumor_text.strip():
        return None, None, None, []

    try:
        # 调用你已建好的系统（带缓存）
        if use_cache:
            result = system.verify_with_cache(rumor_text)
        else:
            result = system.verify(rumor_text)

        # 记录历史
        history_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "query": rumor_text[:100],  # 只存前100字符
            "conclusion": result.get("final_report", "N/A")[:50],  # 结论摘要
            "from_cache": result.get("_from_cache", False)
        }
        query_history.append(history_entry)

        # 准备界面显示的数据
        # 1. 解析结果
        parsed = result.get("parsed_query", {})
        parsed_str = f"**实体**: {parsed.get('entity', 'N/A')}\n"
        parsed_str += f"**主张**: {parsed.get('claim', 'N/A')}\n"
        parsed_str += f"**分类**: {parsed.get('category', 'N/A')}"

        # 2. 关键证据（取前2条）
        evidence_list = result.get("evidence", [])
        top_evidence = "\n\n".join([f"【{i + 1}】{e.get('content', '')}" for i, e in enumerate(evidence_list[:2])])

        # 3. 最终报告
        final_report = result.get("final_report", "未生成报告")

        # 4. 历史记录DataFrame
        history_df = pd.DataFrame(query_history[-10:]) if query_history else pd.DataFrame()

        return parsed_str, top_evidence, final_report, history_df

    except Exception as e:
        error_msg = f"系统处理时出错: {str(e)}"
        return error_msg, "", "", pd.DataFrame()


def save_feedback(rumor_text, is_helpful, feedback_text=""):
    """保存用户反馈到文件"""
    feedback_data = {
        "rumor": rumor_text,
        "is_helpful": is_helpful,
        "feedback": feedback_text,
        "timestamp": datetime.now().isoformat()
    }

    # 保存到JSON文件（可扩展为数据库）
    import json
    try:
        with open("user_feedback.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_data, ensure_ascii=False) + "\n")
        return "✅ 感谢您的反馈！"
    except Exception as e:
        return f"❌ 保存失败: {e}"


# 构建Gradio界面
with gr.Blocks(theme=gr.themes.Soft(), title="谣言鉴定助手") as demo:
    gr.Markdown("# 🕵️ 谣言鉴定助手")
    gr.Markdown("输入一段可疑的传闻，AI将自动解析、检索证据并生成核查报告。")

    with gr.Row():
        with gr.Column(scale=2):
            # 输入区
            input_text = gr.Textbox(
                label="输入待核查的传闻",
                placeholder="例如：吃荔枝后开车会被查出酒驾",
                lines=3
            )
            with gr.Row():
                submit_btn = gr.Button("开始鉴定", variant="primary")
                clear_btn = gr.Button("清空")
            cache_checkbox = gr.Checkbox(label="使用智能缓存（加速重复查询）", value=True)

            # 反馈区
            gr.Markdown("---\n### 反馈")
            with gr.Row():
                helpful_btn = gr.Button("👍 报告有用", size="sm")
                not_helpful_btn = gr.Button("👎 报告无用", size="sm")
            feedback_detail = gr.Textbox(label="详细反馈（可选）", placeholder="请告诉我们如何改进...")
            feedback_output = gr.Textbox(label="反馈结果", interactive=False)

        with gr.Column(scale=3):
            # 输出区
            with gr.Tab("解析结果"):
                parsed_output = gr.Markdown(label="查询解析")
            with gr.Tab("关键证据"):
                evidence_output = gr.Markdown(label="相关证据")
            with gr.Tab("完整报告"):
                report_output = gr.Markdown(label="核查报告")
            with gr.Tab("查询历史"):
                history_output = gr.Dataframe(
                    label="最近10条查询",
                    headers=["时间", "查询", "结论摘要", "缓存"],
                    interactive=False
                )

    # 绑定按钮事件
    submit_btn.click(
        fn=verify_rumor,
        inputs=[input_text, cache_checkbox],
        outputs=[parsed_output, evidence_output, report_output, history_output]
    )

    clear_btn.click(
        lambda: ("", "", "", pd.DataFrame()),
        outputs=[input_text, parsed_output, evidence_output, history_output]
    )

    # 反馈按钮事件
    helpful_btn.click(
        fn=save_feedback,
        inputs=[input_text, gr.State(True), feedback_detail],
        outputs=[feedback_output]
    )

    not_helpful_btn.click(
        fn=save_feedback,
        inputs=[input_text, gr.State(False), feedback_detail],
        outputs=[feedback_output]
    )

    # 示例
    gr.Markdown("---\n### 示例尝试")
    examples = gr.Examples(
        examples=[
            ["吃荔枝后开车会被查出酒驾"],
            ["酸性体质是百病之源，多吃碱性食物可以抗癌"],
            ["WIFI路由器旁边的植物不发芽，证明WIFI辐射会杀死植物"]
        ],
        inputs=[input_text],
        outputs=[parsed_output, evidence_output, report_output, history_output],
        fn=verify_rumor,
        cache_examples=True
    )

if __name__ == "__main__":
    # 启动服务，share=True可生成临时公网链接
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)