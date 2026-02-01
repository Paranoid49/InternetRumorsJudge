# evidence_retriever.py
import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Optional

import config
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("EvidenceRetriever")

# 获取当前文件所在的目录作为基准路径
BASE_DIR = Path(__file__).resolve().parent


class EvidenceKnowledgeBase:
    """
    谣言粉碎机-证据知识库管理类
    
    负责管理本地文档的向量化、存储和检索。
    使用 BAAI/bge-small-zh-v1.5 作为嵌入模型，Chroma 作为向量数据库。
    """

    def __init__(
        self,
        data_dir: str = str(BASE_DIR / "data" / "rumors"),
        persist_dir: str = str(BASE_DIR / "vector_db"),
        embedding_model_name: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu"
    ):
        self.data_dir = Path(data_dir)
        self.persist_dir = Path(persist_dir)
        self.embedding_model_name = embedding_model_name
        self.device = device
        
        # 延迟初始化
        self._embeddings = None
        self._vectorstore = None

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """获取嵌入模型实例（单例模式）"""
        if self._embeddings is None:
            logger.info(f"正在初始化嵌入模型: {self.embedding_model_name} (device={self.device})")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={'device': self.device},
                encode_kwargs={
                    'normalize_embeddings': True,
                    'batch_size': 32  # 批量处理提高效率
                }
            )
        return self._embeddings

    @property
    def vectorstore(self) -> Chroma:
        """获取向量数据库实例"""
        if self._vectorstore is None:
            if not self.persist_dir.exists():
                logger.warning(f"向量库目录 {self.persist_dir} 不存在，将创建一个空的向量库")
            
            self._vectorstore = Chroma(
                persist_directory=str(self.persist_dir),
                embedding_function=self.embeddings,
                collection_metadata={"hnsw:space": "cosine"}  # 显式指定使用余弦相似度
            )
        return self._vectorstore

    def build(self, chunk_size: int = 500, chunk_overlap: int = 50, force: bool = False):
        """
        构建知识库：加载文档 -> 切分 -> 向量化 -> 存储
        
        Args:
            chunk_size: 文本块大小
            chunk_overlap: 文本块重叠大小
            force: 是否强制重建（会删除原有索引）
        """
        if force and self.persist_dir.exists():
            logger.warning(f"强制重建，正在删除旧索引: {self.persist_dir}")
            shutil.rmtree(self.persist_dir)
            # 重置实例
            self._vectorstore = None

        if not self.data_dir.exists():
            raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")

        logger.info(f"开始扫描文档: {self.data_dir}")
        loader = DirectoryLoader(
            str(self.data_dir), 
            glob="**/*.txt", 
            loader_cls=TextLoader,
            loader_kwargs={'encoding': 'utf-8'}
        )
        documents = loader.load()
        
        if not documents:
            logger.warning("未找到任何文档，跳过构建")
            return

        logger.info(f"加载了 {len(documents)} 个文档")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
            keep_separator=True
        )
        chunks = text_splitter.split_documents(documents)
        logger.info(f"切分出 {len(chunks)} 个文本块")

        # Chroma 在 langchain-chroma 中会自动持久化，无需手动调用 persist()
        Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=str(self.persist_dir)
        )
        logger.info(f"✅ 知识库构建完成，已保存至 {self.persist_dir}")

    def get_retriever(self, k: int = 3, score_threshold: Optional[float] = None) -> VectorStoreRetriever:
        """
        获取 LangChain 标准检索器对象
        
        Args:
            k: 返回的最相关文档数量
            score_threshold: 相关性阈值（0-1），如果设置，将只返回相似度高于该阈值的文档
                             如果不设置，将使用 config.SIMILARITY_THRESHOLD
        """
        if score_threshold is None:
            score_threshold = config.SIMILARITY_THRESHOLD

        search_kwargs = {"k": k}
        search_type = "similarity"
        
        if score_threshold is not None:
            search_type = "similarity_score_threshold"
            search_kwargs["score_threshold"] = score_threshold
            
        return self.vectorstore.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )

    def as_search_chain(self, k: int = 3, truncate_len: int = 300, score_threshold: Optional[float] = None):
        """
        创建一个 Runnable 检索链，直接返回格式化好的字典列表。
        适合直接对接前端展示，但不适合作为 RAG 上下文（因文本被截断）。
        
        Args:
            k: 检索数量
            truncate_len: 文本截断长度
            score_threshold: 相似度阈值 (0-1)，如果设置，将只返回高于此相似度的文档
                             如果不设置，将使用 config.SIMILARITY_THRESHOLD
        
        Returns:
            Runnable: 输入 query 字符串，输出 List[Dict]
        """
        # get_retriever 会处理默认值逻辑
        retriever = self.get_retriever(k=k, score_threshold=score_threshold)
        
        def format_docs(docs: List[Document]) -> List[Dict]:
            formatted = []
            for doc in docs:
                content = doc.page_content
                if len(content) > truncate_len:
                     content = content[:truncate_len] + "..."
                
                formatted.append({
                    "content": content,
                    "source": Path(doc.metadata.get("source", "未知")).name
                })
            return formatted

        # 构建链：输入 query -> 检索 -> 格式化
        chain = (
            retriever 
            | RunnableLambda(format_docs)
        )
        return chain

    def search(self, query: str, k: int = 3, score_threshold: Optional[float] = None) -> List[Dict]:
        """
        执行检索并返回结构化结果（适合直接展示或API返回）
        
        Args:
            query: 查询语句
            k: 结果数量
            score_threshold: 相似度阈值 (0-1)，越高越相似。如果设置，将过滤掉相似度低于该值的文档。
                            如果不设置，将使用 config.SIMILARITY_THRESHOLD。
                            注意：内部会自动处理 余弦距离 -> 相似度 的转换。
        """
        if not self.persist_dir.exists():
            logger.error("知识库尚未构建，请先运行 build 命令")
            return []

        if score_threshold is None:
            score_threshold = config.SIMILARITY_THRESHOLD

        logger.info(f"检索: {query}")
        
        # 使用 similarity_search_with_score 可以获取距离分数
        # Chroma 默认是 L2 或 Cosine Distance (越小越相似)
        # 我们这里使用 similarity_search_with_score，它返回的是 distance
        docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=k)
        
        results = []
        for i, (doc, distance) in enumerate(docs_with_scores):
            # 将距离转换为相似度分数 (Assuming Cosine Distance: [0, 2])
            # Similarity = 1 - Distance (如果是 Cosine Similarity)
            # 但 Chroma 的 Cosine distance 范围是 [0, 2]，0 是完全相同，2 是完全相反
            # 不过通常我们在 RAG 中更习惯看 0-1 的相似度。
            # 简单的转换：similarity = 1 - distance (如果 distance 在 0-1 之间)
            # 为了稳妥，我们直接展示 distance，但在过滤时要注意逻辑
            
            # 如果是 Cosine Distance，通常认为 < 0.4 是比较相关的（对应 Cosine Similarity > 0.6）
            # 为了统一接口，我们假设 score_threshold 是针对 "相似度" (0-1, 越大越好)
            # 那么我们需要将 distance 转换为 similarity
            
            # LangChain Chroma 实现中，relevance_score_fn 对于 cosine 是: 1.0 - distance
            similarity_score = 1.0 - distance
            
            if score_threshold is not None and similarity_score < score_threshold:
                continue

            # 智能截断：尝试在句末截断，保持语义完整
            content = doc.page_content
            if len(content) > 200:
                # 在200字符后找最近的句号
                end_pos = 200
                # 简单的寻找句末逻辑，可以根据需要增强
                for char in ['。', '！', '？', '\n']:
                    pos = content.find(char, 150) # 从150字符开始找
                    if pos != -1 and pos < 250: # 如果在合理范围内找到
                        end_pos = pos + 1
                        break
                
                display_content = content[:end_pos] + ("..." if end_pos < len(content) else "")
            else:
                display_content = content

            results.append({
                "rank": i + 1,
                "text": display_content,
                "full_text": content, # 保留完整文本供需要时使用
                "source": Path(doc.metadata.get("source", "未知")).name,
                "score": distance,       # 原始距离分数 (越小越好)
                "similarity": similarity_score, # 相似度分数 (越大越好)
            })
        return results


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="谣言粉碎机 - 证据检索模块")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # Build 命令
    build_parser = subparsers.add_parser("build", help="构建/重建知识库")
    build_parser.add_argument("--force", action="store_true", help="强制删除旧索引并重建")
    build_parser.add_argument("--chunk-size", type=int, default=500, help="文本块大小")

    # Search 命令
    search_parser = subparsers.add_parser("search", help="检索测试")
    search_parser.add_argument("query", type=str, help="查询语句")
    search_parser.add_argument("-k", type=int, default=3, help="返回结果数量")
    search_parser.add_argument("--threshold", type=float, default=None, help=f"相似度阈值 (0-1)，默认: {config.SIMILARITY_THRESHOLD}")

    args = parser.parse_args()
    
    kb = EvidenceKnowledgeBase()
    if args.command == "build":
        kb.build(chunk_size=args.chunk_size, force=args.force)
    elif args.command == "search":
        results = kb.search(args.query, k=args.k, score_threshold=args.threshold)
        if not results:
            print("未找到相关结果 (可能被阈值过滤)。")
        for res in results:
            print(f"\n[#{res['rank']}] (来源: {res['source']})")
            print(f"相似度: {res['similarity']:.4f} (距离: {res['score']:.4f})")
            print("-" * 40)
            print(res['text'][:200] + "..." if len(res['text']) > 200 else res['text'])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
