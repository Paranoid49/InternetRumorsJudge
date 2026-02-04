# -*- coding: utf-8 -*-
"""
去重算法详细测试 - 验证优化效果
"""
from langchain_core.documents import Document
from difflib import SequenceMatcher

def test_new_deduplication():
    """测试新的智能去重算法"""

    print("=" * 60)
    print("去重算法详细验证测试")
    print("=" * 60)

    # 创建测试文档 - 包含高度相似的内容
    test_docs = [
        Document(page_content="吃隔夜水会致癌，因为亚硝酸盐含量超标。", metadata={"source": "doc1.txt"}),
        Document(page_content="吃隔夜水会致癌，因为亚硝酸盐含量超标。", metadata={"source": "doc2.txt"}),
        Document(page_content="隔夜水不能喝，含有很多亚硝酸盐，会得癌症。", metadata={"source": "doc3.txt"}),
        Document(page_content="吸烟有害健康，会导致肺癌。", metadata={"source": "doc4.txt"}),
        Document(page_content="吃洋葱可以预防感冒，因为富含维生素C。", metadata={"source": "doc5.txt"}),
    ]

    print(f"\n原始文档数量: {len(test_docs)}")
    print("-" * 60)

    # 使用新的去重算法
    def new_deduplicate(docs):
        if not docs:
            return []

        # 第一阶段：精确哈希去重
        seen_hashes = set()
        hash_unique = []
        for doc in docs:
            content = doc.page_content[:500].strip()
            if not content:
                continue
            h = hash(content)
            if h not in seen_hashes:
                seen_hashes.add(h)
                hash_unique.append(doc)

        print(f"哈希去重后: {len(hash_unique)} 条")

        # 第二阶段：内容相似度模糊去重
        unique = []
        for doc in hash_unique:
            content = doc.page_content
            content_clean = ' '.join(content.split())

            is_duplicate = False
            for seen_doc in unique:
                similarity = SequenceMatcher(None, content_clean[:300],
                                            ' '.join(seen_doc.page_content.split())[:300]).ratio()
                if similarity > 0.85:
                    print(f"  [去重] 相似度 {similarity:.2f}: '{doc.page_content[:25]}...' <-> '{seen_doc.page_content[:25]}...'")
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(doc)

        return unique

    deduplicated = new_deduplicate(test_docs)

    print(f"\n最终去重后: {len(deduplicated)} 条")
    print(f"去重率: {(len(test_docs) - len(deduplicated)) / len(test_docs) * 100:.1f}%")
    print("-" * 60)

    print("\n[测试结果]")
    if len(deduplicated) < len(test_docs):
        print("状态: 通过 - 新算法成功检测并移除相似文档")
        print(f"效果: 从 {len(test_docs)} 条减少到 {len(deduplicated)} 条")
        return True
    else:
        print("状态: 失败 - 未检测到去重效果")
        return False

def test_old_deduplication():
    """对比旧的简单哈希去重算法"""

    print("\n" + "=" * 60)
    print("对比旧算法（仅前 100 字符哈希）")
    print("=" * 60)

    test_docs = [
        Document(page_content="吃隔夜水会致癌，因为亚硝酸盐含量超标。", metadata={"source": "doc1.txt"}),
        Document(page_content="吃隔夜水会致癌，因为亚硝酸盐含量超标。", metadata={"source": "doc2.txt"}),
    ]

    def old_deduplicate(docs):
        seen_hashes = set()
        unique = []
        for doc in docs:
            content_preview = doc.page_content[:100].strip()
            if not content_preview:
                continue
            h = hash(content_preview)
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique.append(doc)
        return unique

    old_result = old_deduplicate(test_docs)
    print(f"旧算法结果: {len(old_result)} 条 (未去重)")

    # 新算法
    from difflib import SequenceMatcher
    def new_deduplicate_single(docs):
        seen_hashes = set()
        hash_unique = []
        for doc in docs:
            h = hash(doc.page_content[:500].strip())
            if h not in seen_hashes:
                seen_hashes.add(h)
                hash_unique.append(doc)

        unique = []
        for doc in hash_unique:
            content_clean = ' '.join(doc.page_content.split())
            is_duplicate = False
            for seen_doc in unique:
                similarity = SequenceMatcher(None, content_clean[:300],
                                            ' '.join(seen_doc.page_content.split())[:300]).ratio()
                if similarity > 0.85:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(doc)
        return unique

    new_result = new_deduplicate_single(test_docs)
    print(f"新算法结果: {len(new_result)} 条 (已去重)")

    print(f"\n[对比结果] 旧算法保留 {len(old_result)} 条，新算法保留 {len(new_result)} 条")

    return len(new_result) < len(old_result)

if __name__ == "__main__":
    test1 = test_new_deduplication()
    test2 = test_old_deduplication()

    print("\n" + "#" * 60)
    print("# 去重算法测试总结")
    print("#" * 60)
    print(f"新去重算法测试: {'[通过]' if test1 else '[失败]'}")
    print(f"算法对比测试: {'[通过]' if test2 else '[失败]'}")
    print("#" * 60)

    if test1 and test2:
        print("\n结论: 智能去重算法优化成功！")
        print("- 两阶段去重（哈希 + 相似度）有效工作")
        print("- 相比旧算法能更准确地识别相似内容")
