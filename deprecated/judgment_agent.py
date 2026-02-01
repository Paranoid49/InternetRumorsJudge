from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import List, Dict

class JudgmentAgent:
    def __init__(self, llm):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是事实核查的最终裁决员。你的任务是基于所有证据分析，给出综合结论。

请按以下结构组织你的思考：
1. **证据概览**：总结收到了多少证据，其中支持、反对、中立的各有多少。
2. **关键证据评估**：指出权重最高的1-2条证据（通常为：反对/支持立场明确、相关性高、来源可信的证据）。
3. **综合推理**：解释这些证据如何共同指向最终结论。
4. **最终结论**：必须使用以下六种分类之一：
   - **假**：有明确、可信的证据直接反驳主张。
   - **很可能为假**：证据倾向于反驳，但并非绝对确凿。
   - **证据不足**：没有足够的相关证据做出判断。
   - **很可能为真**：证据倾向于支持，但并非绝对确凿。
   - **真**：有明确、可信的证据直接支持主张。
   - **存在争议**：有高质量的证据同时支持和对立，或专家意见分歧。
5. **信心度**：给出一个百分比，表示你对结论的把握。

请生成一份完整、清晰、有说服力的核查报告。"""),
            ("human", """
原始主张：{claim}

所有证据分析结果：
{analysis_results}
""")
        ])
        
        self.judgment_chain = self.prompt | self.llm | StrOutputParser()
    
    def make_judgment(self, claim: str, analysis_results: List[Dict]) -> str:
        """生成最终裁决报告"""
        # 将分析结果格式化为字符串便于模型阅读
        formatted_analysis = "\n\n".join([
            f"证据{i+1}: {res['evidence_text'][:150]}...\n"
            f"  立场: {res['stance']} | 相关性: {res['relevance']} | 可信度: {res['credibility_score']}/5\n"
            f"  理由: {res['reasoning']}"
            for i, res in enumerate(analysis_results)
        ])
        
        return self.judgment_chain.invoke({
            "claim": claim,
            "analysis_results": formatted_analysis
        })