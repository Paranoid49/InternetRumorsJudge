# evaluation.py
import json
from typing import Dict, List
from modern_main import ModernRumorVerificationSystem  # 你的主系统

class RumourEvaluator:
    def __init__(self, system):
        self.system = system
        # 评估数据集 (基于你之前的10条数据，这里以2条为例)
        self.test_dataset = [
            {
                "input": "吃荔枝后开车会被查出酒驾",
                "expected_truth": "假",  # 期望的最终结论
                "expected_entities": ["荔枝", "酒驾"],  # 期望识别出的关键实体
                "category": "生活常识"
            },
            {
                "input": "酸性体质是百病之源，多吃碱性食物可以抗癌",
                "expected_truth": "假",
                "expected_entities": ["酸性体质", "碱性食物", "抗癌"],
                "category": "健康养生"
            }
            # ... 加入你的全部10条数据
        ]
    
    def evaluate_parsing(self, result: Dict, test_case: Dict) -> float:
        """评估查询解析的准确性"""
        score = 0
        parsed = result.get("parsed_query", {})
        
        # 检查是否识别出了核心实体
        detected_entities = parsed.get("entity", "")
        expected_entities = test_case["expected_entities"]
        for exp_entity in expected_entities:
            if exp_entity in detected_entities:
                score += 1
                break
        
        # 检查分类是否正确（如果系统有输出分类）
        if parsed.get("category") == test_case.get("category"):
            score += 1
            
        return score / 2  # 归一化到0-1
    
    def evaluate_retrieval(self, result: Dict) -> float:
        """评估证据检索的相关性"""
        evidence_list = result.get("evidence", [])
        if not evidence_list:
            return 0.0
        
        # 简单评估：是否有证据返回？证据数量是否合理？
        # 更高级的做法：可以用模型评估证据与查询的相关性
        has_evidence = len(evidence_list) > 0
        reasonable_count = 1 <= len(evidence_list) <= 5
        
        return 1.0 if (has_evidence and reasonable_count) else 0.5
    
    def evaluate_judgment(self, final_report: str, test_case: Dict) -> float:
        """评估最终结论的正确性（简化版）"""
        expected = test_case["expected_truth"]
        
        # 在最终报告中查找结论关键词
        report_lower = final_report.lower()
        if expected == "假":
            if "假" in report_lower or "不实" in report_lower or "错误" in report_lower:
                return 1.0
        elif expected == "真":
            if "真" in report_lower or "正确" in report_lower or "属实" in report_lower:
                return 1.0
        # 对于“证据不足”等情况可以扩展
        
        return 0.0
    
    def run_full_evaluation(self) -> Dict:
        """运行完整评估"""
        print("开始全面评估系统性能...")
        print("=" * 60)
        
        total_scores = {"parsing": 0, "retrieval": 0, "judgment": 0}
        
        for i, test_case in enumerate(self.test_dataset):
            print(f"\n🔬 测试案例 {i+1}: {test_case['input']}")
            
            try:
                # 运行系统
                result = self.system.verify(test_case["input"])
                
                # 评估各环节
                parse_score = self.evaluate_parsing(result, test_case)
                retrieval_score = self.evaluate_retrieval(result)
                judgment_score = self.evaluate_judgment(result.get("final_report", ""), test_case)
                
                print(f"  解析评分: {parse_score:.2f}")
                print(f"  检索评分: {retrieval_score:.2f}")
                print(f"  结论评分: {judgment_score:.2f}")
                
                # 累加分数
                total_scores["parsing"] += parse_score
                total_scores["retrieval"] += retrieval_score
                total_scores["judgment"] += judgment_score
                
            except Exception as e:
                print(f"  测试失败: {e}")
                continue
        
        # 计算平均分
        n = len(self.test_dataset)
        avg_scores = {k: v/n for k, v in total_scores.items()}
        avg_scores["overall"] = sum(avg_scores.values()) / len(avg_scores)
        
        print("\n" + "=" * 60)
        print("📊 评估结果汇总:")
        for key, score in avg_scores.items():
            print(f"  {key}: {score:.2%}")
        
        # 生成改进建议
        self.generate_recommendations(avg_scores)
        
        return avg_scores
    
    def generate_recommendations(self, scores: Dict):
        """根据评分生成改进建议"""
        print("\n💡 优化建议:")
        
        if scores["parsing"] < 0.8:
            print("  • 优化查询解析智能体的提示词，确保准确提取实体和主张")
        
        if scores["retrieval"] < 0.7:
            print("  • 检查向量库质量，可能需要：")
            print("    - 增加更多样化的辟谣数据")
            print("    - 调整文本分割策略（chunk_size）")
            print("    - 尝试不同的嵌入模型")
        
        if scores["judgment"] < 0.6:
            print("  • 重点优化分析与裁决智能体：")
            print("    - 在提示词中加入更明确的判断标准")
            print("    - 处理'部分真实'、'证据矛盾'等边缘情况")
            print("    - 让结论与证据的关联更显式")

if __name__ == "__main__":
    # 初始化你的系统
    system = ModernRumorVerificationSystem()
    evaluator = RumourEvaluator(system)
    
    # 运行评估
    results = evaluator.run_full_evaluation()
    
    # 保存评估结果
    with open("evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": "2024-01-01",  # 实际使用时替换为datetime.now()
            "test_cases_count": len(evaluator.test_dataset),
            "scores": results
        }, f, ensure_ascii=False, indent=2)