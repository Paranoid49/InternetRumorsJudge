import os


# ============================================
# 直接集成到 modern_retriever.py 的方法：
# 在 ModernEvidenceRetriever 类中添加以下方法
# ============================================

def create_sample_documents(self):
    """创建示例文档（如果数据目录为空）"""
    import shutil

    sample_dir = "./data/rumors_sample"
    if os.path.exists(sample_dir):
        shutil.rmtree(sample_dir)
    os.makedirs(sample_dir, exist_ok=True)

    # 这里放置上面的数据集...
    sample_data = [...]  # 完整的RUMMOR_DATASET数据

    print(f"📝 创建 {len(sample_data)} 个示例文档...")
    for item in sample_data:
        filename = f"{sample_dir}/{item['id']:02d}_{item['category']}.txt"
        content = f"谣言：{item['rumor']}\n\n辟谣：{item['explanation']}\n\n来源：{item['source']}"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"✅ 示例文档已创建到 {sample_dir}")
    return sample_dir
