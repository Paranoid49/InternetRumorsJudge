import logging
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

import config

logger = logging.getLogger("QueryParser")


class QueryAnalysis(BaseModel):
    entity: str = Field(description="谣言陈述中的核心实体、对象或主体")
    claim: str = Field(description="针对该实体所声称的核心论断或效果")
    category: Literal[
        "健康养生",
        "食品安全",
        "社会事件",
        "科学技术",
        "金融理财",
        "生活常识",
        "其他",
    ] = Field(description="谣言所属的分类")


def build_chain():
    if not config.API_KEY:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY 环境变量")
    model = ChatOpenAI(
        model="qwen3-max",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=config.API_KEY,
        temperature=0.5,
    )
    structured_model = model.with_structured_output(QueryAnalysis)
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """你是一个专业的事实核查助手。请严格分析用户的陈述，并提取关键信息。
                    **输出要求：**
                    1. 必须输出一个合法的JSON对象。
                    2. 严格遵循提供的JSON格式。
                    
                    **分析规则：**
                    - “entity”：提取陈述中最核心、被讨论的主体。
                    - “claim”：精确提取关于该主体的明确声称或断论。
                    - “category”：必须从给定列表中选择最贴切的一个。
                    
                    **示例：**
                    输入："喝隔夜水会致癌"
                    输出：{{"entity": "隔夜水", "claim": "会致癌", "category": "健康养生"}}"""),
        ("human", "用户陈述：{query}"),
    ])
    return prompt_template | structured_model


class QueryParser:
    def __init__(self):
        self.chain = build_chain()

    def parse(self, query: str) -> QueryAnalysis:
        logger.info(f"开始解析查询: '{query}'")
        try:
            result = self.chain.invoke({"query": query})
            if result:
                logger.info(f"解析成功: 实体='{result.entity}', 主张='{result.claim}'")
            return result
        except Exception as e:
            logger.error(f"解析失败: {e}")
            return None

def test_parser():
    test_cases = [
        "吃洋葱能杀死感冒病毒",
        "晚上吃姜等于吃砒霜",
        "手机扫共享单车二维码会中毒",
    ]

    print("开始测试查询解析器...\n")
    parser = QueryParser()
    for i, query in enumerate(test_cases, 1):
        try:
            result = parser.parse(query)
            if result:
                print(f"测试{i}: {query}")
                print(f"   实体: {result.entity}")
                print(f"   主张: {result.claim}")
                print(f"   分类: {result.category}\n")
        except Exception as e:
            print(f"❌ 解析'{query}'时出错: {e}\n")


if __name__ == "__main__":
    test_parser()
