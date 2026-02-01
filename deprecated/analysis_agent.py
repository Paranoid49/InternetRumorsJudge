from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Literal, Optional


# 定义单条证据的分析结果结构
class EvidenceAnalysis(BaseModel):
    evidence_text: str = Field(description="被分析的证据文本片段")
    relevance: Literal["高", "中", "低"] = Field(description="证据与主张的相关性")
    stance: Literal["支持", "反对", "中立", "部分支持/条件性反驳"] = Field(description="证据对主张的立场")
    reasoning: str = Field(description="做出此立场判断的理由，简要说明")
    credibility_score: int = Field(description="证据来源可信度评分，1-5分", ge=1, le=5)


class EnhancedEvidenceAnalysis(EvidenceAnalysis):
    """增强的证据分析结果"""
    nuance_type: Optional[Literal["部分真实", "过时信息", "夸大其词", "断章取义", "概念混淆"]] = Field(
        description="如果存在，指出具体的细微差别类型",
        default=None
    )
    confidence: float = Field(
        description="对此条证据分析的信心度，0-1",
        ge=0.0,
        le=1.0,
        default=0.8
    )
    supporting_quotes: Optional[List[str]] = Field(
        description="从证据中支持判断的关键原文引用",
        default=None
    )

# 更新分析智能体的提示词，加入对复杂情况的处理指引
ENHANCED_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一个资深的事实核查分析员。请以批判性思维评估证据与主张的关系。

特别注意以下复杂情况：
1. **部分真实**：主张包含真实元素但被扭曲或夸大（如“某食物含X物质”是事实，“该物质致癌”是夸大）。
2. **过时信息**：证据或主张基于已被新研究推翻的旧信息。
3. **断章取义**：从真实信息中抽离片段，扭曲原意。
4. **概念混淆**：混淆相关但不同的概念（如“病毒”与“细菌”）。

分析步骤：
1. 提取证据核心主张。
2. 与原始主张逐点对比。
3. 识别逻辑关系（支持/反对/无关）及可能存在的细微差别。
4. 给出信心度并引用关键原文。

输出JSON格式。"""),
    ("human", """
原始主张：{claim}
待分析证据：{evidence}
""")
])

# 定义分析智能体
class AnalysisAgent:
    def __init__(self, llm):
        self.llm = llm
        self.parser = JsonOutputParser(pydantic_object=EnhancedEvidenceAnalysis)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个严谨的事实核查分析员。你的任务是对“证据”与“主张”之间的逻辑关系进行客观评估。

请严格遵循以下步骤分析：
1. 判断相关性：证据文本是否讨论了主张中的实体或核心概念？
2. 判断立场：证据是明确支持、反对、与主张无关，还是给出了有条件的结论？
3. 说明理由：用一句话点明判断的关键逻辑点（例如：证据提供了反例、引用了权威数据、指出了逻辑谬误等）。
4. 评估可信度：根据证据来源的权威性（如官方机构、学术论文、媒体报道、自媒体）给出1-5分。

请仅输出JSON格式。"""),
            ("human", """
请分析以下证据：
主张：{claim}
证据：{evidence}
""")
        ])
        
        self.analysis_chain = self.prompt | self.llm | self.parser
    
    def analyze_single(self, claim: str, evidence: str) -> dict:
        """分析单条证据"""
        return self.analysis_chain.invoke({"claim": claim, "evidence": evidence})
    
    def analyze_all(self, claim: str, evidence_list: List[str]) -> List[dict]:
        """分析所有证据列表"""
        results = []
        for ev in evidence_list:
            try:
                result = self.analyze_single(claim, ev)
                results.append(result)
            except Exception as e:
                print(f"分析证据时出错: {e}")
        return results