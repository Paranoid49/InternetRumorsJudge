import logging
import sys
from pathlib import Path
from typing import List, Literal, Optional
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import config
from src.analyzers.evidence_analyzer import EvidenceAssessment

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
        description="面向用户的简洁报告（200-300字），直接回答：这个说法是真的吗？真相是什么？用通俗语言解释原因，最后给出明确结论。不要提及'证据'、'相关性'、'立场'等技术术语。"
    )
    verdict: VerdictType = Field(
        description="最终结论：真/很可能为真/假/很可能为假/存在争议/证据不足"
    )
    confidence: int = Field(
        description="判断把握度(0-100)。确定结论给高分，不确定给低分。",
        ge=0,
        le=100
    )
    risk_level: Literal["高", "中", "低"] = Field(
        description="潜在危害程度"
    )

class TruthSummarizer:
    """真相总结智能体"""
    
    def __init__(self, model_name: str = None, temperature: float = 0.1):
        if not config.API_KEY:
            raise RuntimeError("未配置 DASHSCOPE_API_KEY 环境变量")

        model_name = model_name or config.MODEL_SUMMARIZER
        self.llm = ChatOpenAI(
            model=model_name,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=config.API_KEY,
            temperature=temperature,
            timeout=getattr(config, 'LLM_REQUEST_TIMEOUT', 30),
            max_tokens=1024,  # 优化: 限制输出长度，提升响应速度
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是面向用户的真相核查助手。直接回答用户：这个说法是真的吗？

**写作要求：**
1. 聚焦用户主张，直接回答真假
2. 用通俗语言解释，不要技术术语
3. 200-300字，简洁明了

**决策标准：**
- 假：有明确可信证据直接反驳
- 很可能为假：证据倾向反驳
- 证据不足：无足够相关证据
- 很可能为真：证据倾向支持
- 真：有明确可信证据直接支持
- 存在争议：高质量证据对立

**必须严格返回JSON，字段名必须完全匹配：**
{{
  "summary": "面向用户的报告...",
  "verdict": "假",
  "confidence": 95,
  "risk_level": "低"
}}
"""),
            ("human", """用户说法：{claim}

参考信息：
{evidence_context}

返回JSON格式报告。"""),
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
            logger.warning("总结中止: 没有收到任何证据评估结果。")
            return FinalVerdict(
                verdict=VerdictType.INSUFFICIENT,
                confidence=0,
                summary="由于未能检索到相关证据或未能完成证据分析，无法对该主张的真实性做出判断。",
                risk_level="低"
            )

        logger.info(f"开始生成真相总结，基于 {len(assessments)} 条证据评估...")
        
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
                result = self.chain.invoke({"claim": claim, "evidence_context": evidence_text})
                if result:
                    logger.info(f"总结生成成功: 结论={result.verdict.value}, 置信度={result.confidence}")
                return result
            except Exception as e:
                logger.warning(f"真相总结生成尝试 {attempt + 1}/{max_retries} 失败: {e}")
                if attempt == max_retries - 1:
                    logger.error("真相总结生成最终失败，已达最大重试次数。启动规则兜底逻辑...")
                    return self._rule_based_fallback(claim, assessments)
        return self._rule_based_fallback(claim, assessments)

    def _rule_based_fallback(self, claim: str, assessments: List[EvidenceAssessment]) -> FinalVerdict:
        """
        基于规则的兜底逻辑：当 LLM 总结失败时，通过统计证据立场给出结论。
        """
        logger.info("执行基于规则的真相总结兜底...")
        
        stance_counts = {
            "支持": 0,
            "反对": 0,
            "中立/不相关": 0,
            "部分支持/条件性反驳": 0
        }
        
        total_weight = 0
        weighted_score = 0 # 支持为 +1, 反对为 -1, 其他为 0
        
        for a in assessments:
            weight = a.authority_score # 权重基于权威性
            stance = a.stance
            if stance in stance_counts:
                stance_counts[stance] += 1
            
            total_weight += weight
            if stance == "支持":
                weighted_score += weight
            elif stance == "反对":
                weighted_score -= weight
            elif stance == "部分支持/条件性反驳":
                weighted_score -= (weight * 0.3) # 偏向质疑

        # 判定逻辑
        if not assessments:
            verdict = VerdictType.INSUFFICIENT
            confidence = 0
        elif weighted_score <= - (total_weight * 0.5):
            verdict = VerdictType.FALSE
            confidence = 80
        elif weighted_score < 0:
            verdict = VerdictType.LIKELY_FALSE
            confidence = 60
        elif weighted_score >= (total_weight * 0.5):
            verdict = VerdictType.TRUE
            confidence = 80
        elif weighted_score > 0:
            verdict = VerdictType.LIKELY_TRUE
            confidence = 60
        else:
            verdict = VerdictType.CONTROVERSIAL
            confidence = 50

        # 构造摘要
        summary = (
            f"【系统自动生成报告（LLM 异常兜底）】\n\n"
            f"针对主张“{claim}”，系统分析了 {len(assessments)} 条证据。\n"
            f"统计结果：{stance_counts['支持']} 条支持，{stance_counts['反对']} 条反对，"
            f"{stance_counts['部分支持/条件性反驳']} 条部分反驳/条件性支持。\n\n"
            f"基于证据立场的加权统计（总权重 {total_weight}，得分 {weighted_score:.1f}），"
            f"初步判定结论为：{verdict.value}。\n"
            f"请注意：此结论由规则引擎自动生成，未经 LLM 深度逻辑润色，仅供参考。"
        )

        return FinalVerdict(
            summary=summary,
            verdict=verdict,
            confidence=confidence,
            risk_level="中"
        )

    def summarize_based_on_knowledge(self, claim: str) -> Optional[FinalVerdict]:
        """基于内部知识进行兜底分析"""
        logger.info(f"开始基于内部知识进行兜底分析: '{claim}'")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = self.fallback_chain.invoke({"claim": claim})
                if result:
                    logger.info(f"兜底总结生成成功: 结论={result.verdict.value}")
                return result
            except Exception as e:
                logger.warning(f"兜底总结生成尝试 {attempt + 1}/{max_retries} 失败: {e}")
                if attempt == max_retries - 1:
                    logger.error("兜底总结最终失败")
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
