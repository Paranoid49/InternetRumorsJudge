import logging
import concurrent.futures
from typing import List, Literal, Dict, Optional
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# 设置项目路径（v0.9.0: 使用统一路径工具）
from src.utils.path_utils import setup_project_path
setup_project_path()

from src import config
from src.utils.llm_factory import create_analyzer_llm

# 导入重试策略（可选）
try:
    from src.core.retry_policy import with_llm_retry
    RETRY_AVAILABLE = True
except ImportError:
    RETRY_AVAILABLE = False

# 导入并行度配置（v0.6.0新增）
try:
    from src.core.parallelism_config import get_parallelism_config
    PARALLELISM_CONFIG_AVAILABLE = True
except ImportError:
    PARALLELISM_CONFIG_AVAILABLE = False

logger = logging.getLogger("EvidenceAnalyzer")

class EvidenceAssessment(BaseModel):
    """单条证据的评估结果"""
    id: int = Field(description="对应输入的证据序号")
    relevance: Literal["高", "中", "低"] = Field(description="该证据与谣言主张的关联程度")
    stance: Literal["支持", "反对", "中立/不相关", "部分支持/条件性反驳"] = Field(description="该证据对主张的立场")
    complexity_label: Literal["无特殊情况", "夸大其词", "过时信息", "断章取义/歪曲事实", "数据错误", "偷换概念", "部分事实"] = Field(
        description="[新] 识别证据揭示的复杂情况。例如：核心事实存在但后果夸大选'夸大其词'；描述旧闻选'过时信息'；引用正确但结论错误选'断章取义'。"
    )
    reason: str = Field(description="判断依据，一句话说明（例如：'该证据引用了专家研究，直接否定了主张中的因果关系'）")
    supporting_quote: str = Field(description="[新] 从证据文本中摘录出支持该判断的最关键原句（引用）")
    confidence: float = Field(description="[新] 对该条分析结果的置信度 (0.0-1.0)", ge=0.0, le=1.0)
    authority_score: int = Field(description="基于证据来源的权威性评分（1-5分）", ge=1, le=5)

class MultiPerspectiveAnalysis(BaseModel):
    """多角度分析结果列表"""
    assessments: List[EvidenceAssessment] = Field(description="对每条证据的分析结果列表")

class EvidenceAnalyzer:
    """证据分析智能体"""
    
    def __init__(self, model_name: str = None, temperature: float = 0.1):  # 优化: 从 0.3 降低到 0.1
        # 优化: 添加快速模式配置
        fast_mode = getattr(config, 'ENABLE_FAST_MODE', False)
        if fast_mode:
            temperature = 0.0  # 快速模式使用确定性输出
            logger.info("启用快速模式：temperature=0.0")

        # 使用统一的 LLM 工厂（v0.9.0）
        self.llm = create_analyzer_llm(temperature=temperature)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的谣言核查分析师。你的任务是深入评估给定的证据相对于某个谣言主张的各项指标，特别是要识别其中的微妙和复杂情况。

                **核心分析维度：**

                1. **相关性 (Relevance)**: 
                   - 高：直接讨论核心实体和事件。
                   - 中：讨论相关话题但未直接针对该主张。
                   - 低：关联微弱或跑题。
                
                2. **立场 (Stance)**:
                   - 支持：证实主张真实。
                   - 反对：证明主张虚假。
                   - 中立/不相关：既不证实也不证伪。
                   - 部分支持/条件性反驳：特定条件下支持或部分反驳。
                
                3. **复杂情况标签 (Complexity Label)** [重要]:
                   请仔细比对主张与证据，识别以下情况：
                   - **夸大其词**: 证据显示主张的核心事件发生过，但后果、规模或严重性被严重放大。（例：某地有轻微地震被传为大毁灭）
                   - **过时信息**: 证据显示主张描述的是过去发生的事，被当作新近发生的。（例：2015年的火灾视频被传为今日发生的）
                   - **断章取义/歪曲事实**: 主张引用了真实来源（如报告、讲话），但故意曲解原意或截取片段以误导。（例：专家说“长期大量吃X有害”，被传为“吃X致癌”）
                   - **数据错误**: 主张中的关键数据（人数、金额、时间）与证据中的权威数据严重不符。
                   - **偷换概念**: 主张将证据中的概念A替换为概念B。（例：将“相关性”替换为“因果性”）
                   - **部分事实**: 主张中包含真实成分，但混杂了虚假信息，无法简单判定真假。
                   - **无特殊情况**: 不属于上述任何一种复杂情况。

                4. **置信度 (Confidence)**:
                   - 对你的分析结果有多大把握（0.0-1.0）。如果证据含糊不清，请降低置信度。

                5. **权威性 (Authority)** (1-5分):
                   - 5分：官方机构(卫健委/WHO)、顶级期刊。
                   - 4分：知名专家、大型商业媒体。
                   - 3分：普通媒体。
                   - 2分：自媒体、论坛。
                   - 1分：来源不明、显然不可靠。
                
                **分析示例 (Few-Shot)**:

                *   **主张**: "吃香蕉会得癌症，因为香蕉有辐射。"
                    **证据**: "香蕉确实含有微量放射性钾-40，但其剂量极低，对人体完全无害，吃香蕉不会致癌。" (来源: 科普中国)
                    **分析**: 立场=反对, 标签=夸大其词/偷换概念, 理由=证据承认有辐射事实，但指出了剂量的安全性，主张抛开剂量谈毒性是夸大危害。, 引用="其剂量极低，对人体完全无害", 置信度=0.95

                *   **主张**: "某地刚刚发生特大爆炸，伤亡惨重！"
                    **证据**: "网传视频实为2015年天津港爆炸视频，近期该地无相关警情。" (来源: 网警辟谣)
                    **分析**: 立场=反对, 标签=过时信息, 理由=主张使用了旧视频来伪造新事件，属于旧闻新炒。, 引用="网传视频实为2015年天津港爆炸视频", 置信度=0.98

                **任务要求：**
                - 必须对提供的每一条证据进行独立分析。
                - 必须返回严格的 JSON 格式。"""),
            ("human", """**谣言主张**：{claim}

                **待分析证据列表**：
                {evidence_text}
                
                请分析上述证据。"""),
        ])

        self.chain = self.prompt | self.llm.with_structured_output(MultiPerspectiveAnalysis)

        # 预过滤配置
        self.enable_prefilter = getattr(config, 'ENABLE_EVIDENCE_PREFILTER', True)
        self.prefilter_max_evidence = getattr(config, 'PREFILTER_MAX_EVIDENCE', 5)
        self.prefilter_min_similarity = getattr(config, 'PREFILTER_MIN_SIMILARITY', 0.3)

    def _prefilter_evidence(self, claim: str, evidence_list: List[Dict]) -> List[Dict]:
        """
        预过滤证据，基于简单规则快速筛选

        规则：
        1. 过滤相似度过低的证据
        2. 限制最大证据数量
        3. 优先保留本地证据（权威性更高）
        """
        if not self.enable_prefilter:
            return evidence_list

        logger.info(f"预过滤: {len(evidence_list)} 条证据 -> ...")

        # 1. 过滤相似度过低的证据
        filtered = []
        for ev in evidence_list:
            similarity = ev.get('metadata', {}).get('similarity', 0.0)
            # 如果有similarity字段，过滤低于阈值的
            if similarity >= self.prefilter_min_similarity or similarity == 0.0:
                filtered.append(ev)

        if len(filtered) < len(evidence_list):
            logger.info(f"相似度过滤: {len(evidence_list)} -> {len(filtered)}")

        # 2. 优先保留本地证据（权威性更高）
        local_evidence = [ev for ev in filtered if ev.get('metadata', {}).get('type') == 'local']
        web_evidence = [ev for ev in filtered if ev.get('metadata', {}).get('type') == 'web']

        # 3. 限制最大数量（本地证据优先）
        selected = local_evidence[:self.prefilter_max_evidence]
        remaining_slots = self.prefilter_max_evidence - len(selected)

        if remaining_slots > 0 and web_evidence:
            selected.extend(web_evidence[:remaining_slots])

        logger.info(f"预过滤完成: {len(evidence_list)} -> {len(selected)} 条证据 (节省 {len(evidence_list) - len(selected)} 条LLM分析)")

        return selected

    def analyze(self, claim: str, evidence_list: List[Dict], chunk_size: int = 2) -> List[EvidenceAssessment]:
        """
        执行分析，如果证据较多则采用并行处理以提高速度。

        优化: 降低 chunk_size 到 2，触发更积极的并行策略

        新增：预过滤机制，降低API成本
        """
        if not evidence_list:
            logger.warning("分析中止: 传入的证据列表为空。")
            return []

        # 预过滤证据（降低LLM调用次数）
        evidence_list = self._prefilter_evidence(claim, evidence_list)

        if not evidence_list:
            logger.warning("预过滤后无证据，跳过分析")
            return []

        count = len(evidence_list)

        # 优化: 优先使用单证据并行分析（适用于 2-5 个证据）
        if 2 <= count <= 5:
            logger.info(f"证据数量({count})适合单证据并行分析")
            return self._analyze_parallel_single(claim, evidence_list)

        if count <= chunk_size:
            # 数量较少，直接单次请求
            return self._analyze_batch(claim, evidence_list, offset=0)
        
        # 数量较多，分片并行分析
        logger.info(f"证据数量({count})超过分片阈值({chunk_size})，启动并行分析...")
        chunks = [evidence_list[i:i + chunk_size] for i in range(0, count, chunk_size)]
        
        # [v0.6.0] 使用动态并行度配置
        if PARALLELISM_CONFIG_AVAILABLE:
            max_workers = get_parallelism_config().get_adaptive_workers(
                task_count=len(chunks),
                task_type='evidence_analyzer',
                min_workers=1
            )
            logger.info(f"动态并行度: {max_workers} (批次数: {len(chunks)})")
        else:
            max_workers = min(len(chunks), 5)  # 回退到硬编码值

        all_assessments = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(self._analyze_batch, claim, chunk, i * chunk_size): i
                for i, chunk in enumerate(chunks)
            }
            
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    batch_results = future.result()
                    all_assessments.extend(batch_results)
                except Exception as e:
                    logger.error(f"分片分析失败: {e}")
        
        # 按 ID 排序确保顺序一致
        all_assessments.sort(key=lambda x: x.id)
        return all_assessments

    def _analyze_parallel_single(self, claim: str, evidence_list: List[Dict]) -> List[EvidenceAssessment]:
        """
        每个证据单独并行分析（优化方案1）

        适用于 2-5 个证据的场景，每个证据独立并行分析
        """
        if not evidence_list:
            return []

        logger.info(f"启用单证据并行分析: {len(evidence_list)} 条证据")

        # [v0.6.0] 使用动态并行度配置
        if PARALLELISM_CONFIG_AVAILABLE:
            max_workers = get_parallelism_config().get_adaptive_workers(
                task_count=len(evidence_list),
                task_type='evidence_analyzer',
                min_workers=1
            )
            logger.info(f"动态并行度: {max_workers} (证据数: {len(evidence_list)})")
        else:
            max_workers = min(len(evidence_list), 5)  # 回退到硬编码值

        all_assessments = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 每个证据单独提交
            future_to_evidence = {
                executor.submit(self._analyze_single_evidence, claim, ev, i): i
                for i, ev in enumerate(evidence_list)
            }

            for future in concurrent.futures.as_completed(future_to_evidence):
                try:
                    assessment = future.result()
                    all_assessments.append(assessment)
                except Exception as e:
                    logger.error(f"证据分析失败: {e}")

        # 按 ID 排序确保顺序一致
        all_assessments.sort(key=lambda x: x.id)
        return all_assessments

    def _analyze_single_evidence(self, claim: str, evidence: Dict, index: int) -> EvidenceAssessment:
        """
        分析单个证据（用于并行调用）

        复用 _analyze_batch 的逻辑，但只处理一个证据
        """
        results = self._analyze_batch(claim, [evidence], offset=index)
        return results[0] if results else None

    def _analyze_batch(self, claim: str, evidence_list: List[Dict], offset: int = 0) -> List[EvidenceAssessment]:
        """内部执行单次批量的分析请求"""
        logger.info(f"正在分析 {len(evidence_list)} 条证据 (偏移量: {offset})...")
        
        # 格式化证据文本，注意 ID 要加上偏移量
        evidence_text_lines = []
        for i, ev in enumerate(evidence_list):
            idx = offset + i + 1
            source = ev.get('source', '未知来源')
            text = ev.get('text', '').replace('\n', ' ')
            evidence_text_lines.append(f"证据 #{idx} [来源: {source}]: {text}")
        
        formatted_evidence_text = "\n\n".join(evidence_text_lines)
        
        try:
            result: MultiPerspectiveAnalysis = self.chain.invoke({
                "claim": claim,
                "evidence_text": formatted_evidence_text
            })
            # 校验 ID 是否正确（LLM 有时会乱写 ID，我们根据偏移量强行校准一遍）
            for i, assessment in enumerate(result.assessments):
                if i < len(evidence_list):
                    assessment.id = offset + i + 1
            
            return result.assessments
        except Exception as e:
            logger.error(f"单次批量分析过程出错: {e}")
            return []

# 保持函数式接口以便兼容现有代码
def analyze_evidence(claim: str, evidence_list: List[Dict]) -> List[EvidenceAssessment]:
    analyzer = EvidenceAnalyzer()
    return analyzer.analyze(claim, evidence_list)
