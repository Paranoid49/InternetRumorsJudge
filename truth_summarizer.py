import logging
from typing import List, Literal, Optional
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import config
from evidence_analyzer import EvidenceAssessment

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VerdictType(str, Enum):
    TRUE = "真"
    LIKELY_TRUE = "很可能为真"
    FALSE = "假"
    LIKELY_FALSE = "很可能为假"
    CONTROVERSIAL = "存在争议"
    INSUFFICIENT = "证据不足"

class FinalVerdict(BaseModel):
    summary: str = Field(
        description="详细的核查报告。请按以下结构撰写：\n1. 证据概览（收到了多少证据，支持/反对情况）；\n2. 关键证据评估（指出权重最高的证据及其理由）；\n3. 综合推理（逻辑链条）；\n4. 最终结论陈述。"
    )
    verdict: VerdictType = Field(
        description="最终的核查结论。请基于上述总结，从提供的6个选项中选择最贴切的一个。"
    )
    confidence: int = Field(
        description="你对这个判断有多大的把握？(0-100)。\n注意：即使结论是'假'，如果你非常确定它是假的，也应该给高分（如 90-100）。只有当你觉得证据不足、不确定时才给低分。", 
        ge=0, 
        le=100
    )
    risk_level: Literal["高", "中", "低"] = Field(
        description="该谣言/信息的潜在危害程度。"
    )

class TruthSummarizer:
    """真相总结智能体"""
    
    def __init__(self, model_name: str = "qwen3-max", temperature: float = 0.4):
        if not config.API_KEY:
            raise RuntimeError("未配置 DASHSCOPE_API_KEY 环境变量")

        self.llm = ChatOpenAI(
            model=model_name,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=config.API_KEY,
            temperature=temperature,
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是事实核查的最终裁决员。你的任务是基于所有证据分析，给出综合结论。

                **决策逻辑与步骤：**
                1. **证据概览**：统计支持、反对、中立的证据数量。
                2. **关键证据评估**：找出权威性最高（4-5分）且相关性高的证据。若权威证据与小道消息冲突，以权威为准。
                3. **综合推理**：解释证据如何指向结论。
                4. **定性判断**：
                   - **假**：有明确、可信的证据直接反驳主张。
                   - **很可能为假**：证据倾向于反驳，但并非绝对确凿。
                   - **证据不足**：没有足够的相关证据做出判断。
                   - **很可能为真**：证据倾向于支持，但并非绝对确凿。
                   - **真**：有明确、可信的证据直接支持主张。
                   - **存在争议**：有高质量的证据同时支持和对立，或专家意见分歧。
                
                **输出要求：**
                - 必须返回严格的 JSON 格式。
                - summary 字段应是一篇逻辑通顺、可读性强的文章。
                - confidence 字段必须表示对“裁决结果”的信心。例如：你裁决为“假”，且证据确凿，confidence 应为 100。"""),
            ("human", """**原始主张**：{claim}

                **证据分析结果**：
                {evidence_context}
                
                请生成最终裁决报告。"""),
        ])
        
        self.chain = self.prompt | self.llm.with_structured_output(FinalVerdict)
        
        # 添加基于内部知识的 fallback prompt
        self.fallback_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是事实核查专家。目前的本地知识库中没有找到关于用户主张的直接证据。
                
                **你的任务**：
                请调用你作为大型语言模型的内部广泛知识库，对该主张进行初步的常识性判断。
                
                **特别注意**：
                1. **必须诚实**：如果你不知道，或该信息属于高度专业/最新的领域且你不确定，请直接判定为“证据不足”。
                2. **明确来源**：在总结报告中必须明确指出“警告：本地知识库未命中，以下结论仅基于通用知识，建议进一步核实”。
                3. **定性判断**：
                   - 如果是公认的科学常识（如“吸烟有害健康”），可以判定为“真”或“假”。
                   - 如果是流传甚广的谣言（如“食物相克”），可以依据常识判定。
                   - 如果是不确定的、具体的近期新闻或模糊信息，选择“证据不足”。
                
                **输出要求**：
                返回与标准流程一致的 JSON 格式。"""),
            ("human", "主张：{claim}\n\n请基于你的内部知识进行核查。"),
        ])
        
        self.fallback_chain = self.fallback_prompt | self.llm.with_structured_output(FinalVerdict)

    def summarize(self, claim: str, assessments: List[EvidenceAssessment]) -> Optional[FinalVerdict]:
        """执行总结"""
        if not assessments:
            # 修改原有逻辑，不再直接返回 INSUFFICIENT，而是留给调用方处理，或者在这里抛出异常/返回特定状态
            # 但为了兼容性，如果 assessments 为空且未调用 fallback，这里仍然保持原样比较安全，
            # 或者调用方应该显式调用 summarize_based_on_knowledge。
            # 暂时保持原样，新增方法供 pipeline 调用。
            logger.warning("没有收到证据分析结果，无法生成真相总结")
            return FinalVerdict(
                verdict=VerdictType.INSUFFICIENT,
                confidence=0,
                summary="由于未能检索到相关证据或未能完成证据分析，无法对该主张的真实性做出判断。",
                risk_level="低"
            )

        # 格式化上下文
        evidence_context = []
        for a in assessments:
            evidence_context.append(
                f"证据 #{a.id}:\n"
                f"  - 相关性: {a.relevance}\n"
                f"  - 立场: {a.stance}\n"
                f"  - 权威性: {a.authority_score}/5\n"
                f"  - 理由: {a.reason}\n"
            )
        
        evidence_text = "\n".join(evidence_context)
        
        # 增加重试机制，应对 JSON 解析不稳定问题
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.chain.invoke({"claim": claim, "evidence_context": evidence_text})
            except Exception as e:
                logger.warning(f"真相总结生成尝试 {attempt + 1}/{max_retries} 失败: {e}")
                if attempt == max_retries - 1:
                    logger.error("真相总结生成最终失败，已达最大重试次数")
                    return None
        return None

    def summarize_based_on_knowledge(self, claim: str) -> Optional[FinalVerdict]:
        """基于内部知识进行兜底分析"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.fallback_chain.invoke({"claim": claim})
            except Exception as e:
                logger.warning(f"兜底总结生成尝试 {attempt + 1}/{max_retries} 失败: {e}")
                if attempt == max_retries - 1:
                    return None
        return None

# 保持函数式接口
def summarize_truth(claim: str, assessments: List[EvidenceAssessment]) -> Optional[FinalVerdict]:
    summarizer = TruthSummarizer()
    return summarizer.summarize(claim, assessments)

def summarize_with_fallback(claim: str) -> Optional[FinalVerdict]:
    """新暴露的兜底函数"""
    summarizer = TruthSummarizer()
    return summarizer.summarize_based_on_knowledge(claim)

if __name__ == "__main__":
    # 测试代码
    test_claim = "喝隔夜水会致癌"
    test_assessments = [
        EvidenceAssessment(id=1, relevance="高", stance="反对", reason="央视实验证明亚硝酸盐含量远低于国标", authority_score=5),
        EvidenceAssessment(id=2, relevance="高", stance="反对", reason="专家指出致癌需要极大量", authority_score=4),
    ]
    
    print("正在生成测试总结...")
    verdict = summarize_truth(test_claim, test_assessments)
    if verdict:
        print(f"结论: {verdict.verdict.value}")
        print(f"置信度: {verdict.confidence}")
        print(f"风险: {verdict.risk_level}")
        print(f"总结报告:\n{verdict.summary}")
