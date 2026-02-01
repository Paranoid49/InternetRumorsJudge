#!/usr/bin/env python3
"""
谣言数据生成脚本
运行: python create_rumor_data.py
将在 data/ 目录下生成两种格式的数据
"""
import os
import json
from datetime import datetime

from internet_rumors_judge.prepare_data.create_data import RUMMOR_DATASET


# 完整的谣言数据集（同上，已省略以节省空间，请将上面完整的RUMMOR_DATASET复制到这里）

def create_data_directory():
    """创建数据目录结构"""
    directories = [
        "data",
        "data/rumors_txt",
        "data/vector_db"
    ]

    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)
        print(f"📁 创建目录: {dir_path}")


def save_as_json(data):
    """保存为JSON文件"""
    json_path = "../data/rumors_dataset.json"

    # 添加元数据
    dataset_info = {
        "name": "中文谣言鉴定数据集",
        "version": "1.0",
        "created_date": datetime.now().strftime("%Y-%m-%d"),
        "count": len(data),
        "description": "用于训练和测试谣言鉴定AI助手的数据集",
        "categories": list(set([item["category"] for item in data])),
        "data": data
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset_info, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON数据已保存: {json_path}")
    print(f"   包含 {len(data)} 条谣言数据，{len(dataset_info['categories'])} 个类别")

    return json_path


def save_as_txt_files(data):
    """保存为多个TXT文件（适合文档加载器）"""
    txt_count = 0

    for item in data:
        # 创建安全的文件名
        safe_title = "".join(c for c in item["rumor"][:30] if c.isalnum() or c in ("_", " "))
        filename = f"{item['id']:02d}_{safe_title}.txt"
        filepath = os.path.join("data/rumors_txt", filename)

        # 格式化内容
        content = f"""标题：【辟谣】关于“{item['rumor']}”的真实情况
分类：{item['category']}
真实性：{item['truth']}
发布日期：{item['date']}
数据编号：RUMOR-{item['id']:03d}
来源：{item['source']}
标签：{', '.join(item['tags'])}

【谣言内容】
{item['rumor']}

【真相核查】
{item['explanation']}

【关键事实】
{chr(10).join(f'• {fact}' for fact in item['key_facts'])}

【结论】
经核查，“{item['rumor']}”为不实信息。建议广大网民不传谣、不信谣，从权威渠道获取信息。
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        txt_count += 1

    print(f"✅ TXT文件已保存: data/rumors_txt/")
    print(f"   生成 {txt_count} 个文本文件")

    return txt_count


def save_as_single_txt(data):
    """保存为单个大文本文件（备用）"""
    content_lines = []

    for item in data:
        content_lines.append(f"{'=' * 60}")
        content_lines.append(f"ID: {item['id']}")
        content_lines.append(f"谣言: {item['rumor']}")
        content_lines.append(f"分类: {item['category']}")
        content_lines.append(f"真相: {item['truth']}")
        content_lines.append(f"来源: {item['source']}")
        content_lines.append(f"日期: {item['date']}")
        content_lines.append(f"标签: {', '.join(item['tags'])}")
        content_lines.append("")
        content_lines.append("详细解释:")
        content_lines.append(item['explanation'])
        content_lines.append("")
        content_lines.append("关键事实:")
        for fact in item['key_facts']:
            content_lines.append(f"  • {fact}")
        content_lines.append("")

    single_txt_path = "../data/all_rumors.txt"
    with open(single_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content_lines))

    print(f"✅ 合并文本已保存: {single_txt_path}")

    return single_txt_path


def create_modern_retriever_integration_code():
    """生成可直接集成到modern_retriever.py的代码"""
    integration_code = '''
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
        content = f"谣言：{item['rumor']}\\n\\n辟谣：{item['explanation']}\\n\\n来源：{item['source']}"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"✅ 示例文档已创建到 {sample_dir}")
    return sample_dir
'''

    code_path = "../data/integration_example.py"
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(integration_code)

    print(f"📦 集成示例代码: {code_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("谣言数据集生成工具")
    print("=" * 60)

    # 创建目录结构
    create_data_directory()

    # 使用完整的数据集（请确保RUMMOR_DATASET已定义）
    # 这里需要你将上面的完整RUMMOR_DATASET复制到此处

    # 保存为不同格式
    json_file = save_as_json(RUMMOR_DATASET)
    txt_count = save_as_txt_files(RUMMOR_DATASET)
    single_txt = save_as_single_txt(RUMMOR_DATASET)

    # 生成集成代码
    create_modern_retriever_integration_code()

    print("\n" + "=" * 60)
    print("🎉 数据生成完成！")
    print("=" * 60)
    print("生成的格式：")
    print(f"  1. JSON格式: {json_file}")
    print(f"  2. TXT文档: data/rumors_txt/ ({txt_count}个文件)")
    print(f"  3. 合并文本: {single_txt}")
    print("\n使用建议：")
    print("  • 使用TXT文档测试modern_retriever.py的文档加载功能")
    print("  • 使用JSON数据进行程序化处理")
    print("  • 运行: python modern_retriever.py 构建向量库")

    # 显示统计信息
    categories = {}
    for item in RUMMOR_DATASET:
        cat = item["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print("\n📊 数据集统计：")
    print(f"  总条目数: {len(RUMMOR_DATASET)}")
    print(f"  类别分布: {categories}")
    print(f"  时间范围: {min([item['date'] for item in RUMMOR_DATASET])} 至 "
          f"{max([item['date'] for item in RUMMOR_DATASET])}")


if __name__ == "__main__":
    # 注意：需要将完整的RUMMOR_DATASET列表复制到这里
    main()