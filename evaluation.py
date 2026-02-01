import time
import os
import sys
import json
import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from colorama import init, Fore, Style

# 初始化模块
from query_parser import QueryParser
from evidence_retriever import EvidenceKnowledgeBase
from evidence_analyzer import EvidenceAnalyzer
from truth_summarizer import TruthSummarizer, VerdictType

# 初始化 colorama
init(autoreset=True)

@dataclass
class TestCase:
    id: int
    query: str
    expected_entity: str
    expected_claim: str
    target_file_keyword: str
    expected_verdict: str  # "假" or "很可能为假"

@dataclass
class EvaluationResult:
    case_id: int
    parsing_score: float
    retrieval_score: float
    verdict_score: float
    total_score: float
    details: str

class RumorSystemEvaluator:
    def __init__(self):
        print(f"{Fore.CYAN}正在初始化评估系统...{Style.RESET_ALL}")
        self.parser = QueryParser()
        self.retriever = EvidenceKnowledgeBase()
        self.analyzer = EvidenceAnalyzer()
        self.summarizer = TruthSummarizer()
        
        # 10条测试数据
        self.test_cases = [
            TestCase(1, "听说喝隔夜水会致癌", "隔夜水", "致癌", "11_隔夜水致癌", "假"),
            TestCase(2, "吃荔枝真的会被查出酒驾吗", "荔枝", "酒驾", "01_吃荔枝后开车会被查出酒驾", "假"), # 实际上是假谣言（真有此事），但结论通常是“真的但很快消散”或者“部分属实”，这里我们主要看系统能否检索到
            TestCase(3, "酸性体质是百病之源，要多吃碱性食物抗癌", "酸性体质", "抗癌", "02_酸性体质", "假"),
            TestCase(4, "5G基站会传播新冠病毒", "5G", "传播病毒", "44_5G传播新冠病毒", "假"),
            TestCase(5, "看到地震云是不是马上要地震了", "地震云", "地震", "60_地震云能预测地震", "假"),
            TestCase(6, "适量喝酒到底有没有益健康", "喝酒", "有益健康", "89_适量喝酒有益健康", "假"),
            TestCase(7, "喝蛋白粉会不会伤肾", "蛋白粉", "伤肾", "93_蛋白粉伤肾", "假"),
            TestCase(8, "手机信号剩一格辐射特别大", "手机信号", "辐射", "105_手机信号", "假"),
            TestCase(9, "把手机壁纸设成绿色能护眼吗", "壁纸", "护眼", "113_看绿色护眼", "假"),
            TestCase(10, "虾和维生素C一起吃会中毒吗", "虾", "中毒", "15_虾和维生素C", "假")
        ]

    def evaluate_parsing(self, case: TestCase, parsed_result) -> float:
        score = 0.0
        if not parsed_result:
            return 0.0
        
        # 实体匹配 (0.5分)
        if case.expected_entity in parsed_result.entity:
            score += 5.0
        
        # 主张匹配 (0.5分)
        if case.expected_claim in parsed_result.claim:
            score += 5.0
            
        return score

    def evaluate_retrieval(self, case: TestCase, evidences: List[Dict]) -> float:
        if not evidences:
            return 0.0
        
        # 检查前3个结果中是否包含目标文件
        for i, doc in enumerate(evidences[:3]):
            source = doc.get('source', '')
            if case.target_file_keyword in source:
                # 第1名: 10分, 第2名: 8分, 第3名: 6分
                return 10.0 - (i * 2)
        
        return 0.0

    def evaluate_verdict(self, case: TestCase, verdict) -> float:
        if not verdict:
            return 0.0
        
        # 简化版逻辑：只要是 假 或 很可能为假，就得分
        # 注意：部分测试用例（如荔枝酒驾）可能是“部分支持”或“真”，这里需特殊处理或调整预期
        # 鉴于我们的数据多为谣言，预期多为“假”
        
        v_str = verdict.verdict.value
        
        if v_str == "假":
            return 10.0
        elif v_str == "很可能为假":
            return 8.0
        elif v_str == "存在争议": # 视情况给分
            return 5.0
        elif v_str == "真" and case.id == 2: # 荔枝酒驾确实存在瞬间酒精反应
             return 10.0
        elif v_str == "很可能为真" and case.id == 2:
             return 8.0
             
        # 如果方向完全错了
        return 0.0

    def generate_recommendations(self, avg_scores: Dict[str, float]):
        """根据评分生成改进建议"""
        print(f"\n{Fore.CYAN}💡 优化建议:{Style.RESET_ALL}")
        
        parsing_rate = avg_scores["parsing"]
        retrieval_rate = avg_scores["retrieval"]
        verdict_rate = avg_scores["verdict"]

        if parsing_rate < 0.8:
            print("  • 优化查询解析智能体的提示词，确保准确提取实体和主张")
        
        if retrieval_rate < 0.7:
            print("  • 检查向量库质量，可能需要：")
            print("    - 增加更多样化的辟谣数据")
            print("    - 调整文本分割策略（chunk_size）")
            print("    - 尝试不同的嵌入模型")
        elif retrieval_rate < 0.9:
            print("  • 检索效果尚可，但仍有提升空间，建议检查漏检的特定案例（如：关键词匹配问题）。")

        if verdict_rate < 0.6:
            print("  • 重点优化分析与裁决智能体：")
            print("    - 在提示词中加入更明确的判断标准")
            print("    - 处理'部分真实'、'证据矛盾'等边缘情况")
            print("    - 让结论与证据的关联更显式")
        elif verdict_rate < 0.8:
             print("  • 裁决模块偶尔失误，建议分析错误案例，微调Prompt对“证据不足”或“部分支持”的判定逻辑。")

        if parsing_rate >= 0.9 and retrieval_rate >= 0.9 and verdict_rate >= 0.9:
            print("  • 系统表现卓越！可以考虑引入更多边缘测试用例（如对抗样本）进行压力测试。")

    def run(self):
        print(f"\n{Fore.GREEN}=== 开始全面评估 (共{len(self.test_cases)}条测试数据) ==={Style.RESET_ALL}\n")
        
        results = []
        
        for case in self.test_cases:
            print(f"正在评估 Case #{case.id}: {case.query} ... ", end="", flush=True)
            
            # 1. 解析
            parsed = self.parser.parse(case.query)
            p_score = self.evaluate_parsing(case, parsed)
            
            # 2. 检索
            evidences = []
            r_score = 0.0
            if parsed:
                # 组合查询词
                query_text = f"{parsed.entity} {parsed.claim}"
                evidences = self.retriever.search(query_text, k=3)
                r_score = self.evaluate_retrieval(case, evidences)
            
            # 3. 分析 & 4. 裁决
            v_score = 0.0
            verdict_text = "N/A"
            if evidences:
                assessments = self.analyzer.analyze(parsed.claim, evidences)
                final_verdict = self.summarizer.summarize(parsed.claim, assessments)
                v_score = self.evaluate_verdict(case, final_verdict)
                if final_verdict:
                    verdict_text = final_verdict.verdict.value

            total = p_score + r_score + v_score
            
            # 记录结果
            res = EvaluationResult(
                case_id=case.id,
                parsing_score=p_score,
                retrieval_score=r_score,
                verdict_score=v_score,
                total_score=total,
                details=f"解析: {parsed.entity if parsed else 'None'} | 检索命中: {'是' if r_score > 0 else '否'} | 结论: {verdict_text}"
            )
            results.append(res)
            print(f"{Fore.GREEN}完成{Style.RESET_ALL} (得分: {total}/30)")

        avg_scores = self.print_report(results)
        self.generate_recommendations(avg_scores)
        self.save_results(results, avg_scores)

    def print_report(self, results: List[EvaluationResult]) -> Dict[str, float]:
        print(f"\n{Fore.YELLOW}=== 评估报告 ==={Style.RESET_ALL}")
        print(f"{'ID':<4} {'解析(10)':<10} {'检索(10)':<10} {'结论(10)':<10} {'总分(30)':<10} {'详情'}")
        print("-" * 80)
        
        total_p = 0
        total_r = 0
        total_v = 0
        grand_total = 0
        
        for r in results:
            print(f"{r.case_id:<4} {r.parsing_score:<10} {r.retrieval_score:<10} {r.verdict_score:<10} {r.total_score:<10} {r.details}")
            total_p += r.parsing_score
            total_r += r.retrieval_score
            total_v += r.verdict_score
            grand_total += r.total_score
            
        avg_score = grand_total / len(results)
        
        print("-" * 80)
        print(f"平均分: {avg_score:.2f} / 30")
        
        # 分级
        grade = "C"
        if avg_score >= 27: grade = "S (卓越)"
        elif avg_score >= 24: grade = "A (优秀)"
        elif avg_score >= 18: grade = "B (良好)"
        
        print(f"系统评级: {Fore.RED if grade=='C' else Fore.GREEN}{grade}{Style.RESET_ALL}")
        
        # 维度分析
        p_rate = total_p / (len(results)*10)
        r_rate = total_r / (len(results)*10)
        v_rate = total_v / (len(results)*10)

        print(f"\n维度得分率:")
        print(f"  - 查询解析: {p_rate * 100:.1f}%")
        print(f"  - 证据检索: {r_rate * 100:.1f}%")
        print(f"  - 最终裁决: {v_rate * 100:.1f}%")

        return {"parsing": p_rate, "retrieval": r_rate, "verdict": v_rate, "overall": avg_score}

    def save_results(self, results: List[EvaluationResult], avg_scores: Dict[str, float]):
        """保存评估结果到JSON文件"""
        output_file = "evaluation_results.json"
        try:
            data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "test_cases_count": len(results),
                "summary": {
                    "average_score": avg_scores["overall"],
                    "dimension_scores": {k: v for k, v in avg_scores.items() if k != "overall"}
                },
                "details": [asdict(r) for r in results]
            }
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n{Fore.BLUE}✅ 评估结果已保存至: {output_file}{Style.RESET_ALL}")
        except Exception as e:
            print(f"\n{Fore.RED}❌ 保存结果失败: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    evaluator = RumorSystemEvaluator()
    evaluator.run()
