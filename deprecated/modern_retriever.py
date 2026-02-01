# modern_retriever.py - 完全现代LangChain写法
import os
from pathlib import Path
from typing import List, Dict, Optional

# 1. 现代导入方式 - 每个功能有独立的专门包
from langchain_chroma import Chroma  # 专用Chroma包
from langchain_huggingface import HuggingFaceEmbeddings  # 专用嵌入模型包
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 专用文本分割包
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_core.runnables import RunnablePassthrough

class ModernEvidenceRetriever:
    """现代写法的证据检索智能体"""
    
    def __init__(self, data_path: str = "./data/rumors"):
        self.data_path = Path(data_path)
        self.vectorstore: Optional[Chroma] = None
        self.retriever: Optional[VectorStoreRetriever] = None
        
        # 使用更现代的嵌入模型配置
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",
            model_kwargs={"device": "cpu"},
            encode_kwargs={
                "normalize_embeddings": True,
                "batch_size": 32  # 批量处理提高效率
            }
        )
        print("✅ 现代嵌入模型初始化完成")
    
    def build_knowledge_base(self, chunk_size: int = 400, chunk_overlap: int = 80):
        """构建知识库 - 使用现代参数配置"""
        
        # 1. 加载文档（使用pathlib更现代）
        if not self.data_path.exists():
            self.data_path.mkdir(parents=True, exist_ok=True)
            print(f"⚠️  数据目录 {self.data_path} 已创建，请添加 .txt 文档")
            return False
        
        loader = DirectoryLoader(
            str(self.data_path), 
            glob="**/*.txt", 
            loader_cls=TextLoader,
            loader_kwargs={"autodetect_encoding": True}  # 自动检测编码
        )
        
        documents = loader.load()
        if not documents:
            print("❌ 未找到文档，请在 data/rumors/ 中添加 .txt 文件")
            return False
            
        print(f"📚 已加载 {len(documents)} 个文档")
        
        # 2. 文本分割 - 更智能的分割方式
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
            keep_separator=True  # 保留分隔符，维护上下文
        )
        
        chunks = text_splitter.split_documents(documents)
        print(f"✂️  分割为 {len(chunks)} 个文本块")
        
        # 3. 创建向量存储 - 使用现代Chroma集成
        self.vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory="./modern_vector_db",  # 使用新目录避免冲突
            collection_metadata={"hnsw:space": "cosine"}  # 优化相似度计算
        )
        
        # 4. 创建检索器 - 更灵活的配置
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",  # 或 "mmr" 最大边际相关性
            search_kwargs={
                "k": 4,  # 返回4条证据
                "score_threshold": 0.5  # 最低相关性阈值
            }
        )
        
        print("✅ 现代化知识库构建完成")
        return True
    
    def load_existing_knowledge_base(self) -> bool:
        """加载现有知识库"""
        if Path("./modern_vector_db").exists():
            self.vectorstore = Chroma(
                persist_directory="./modern_vector_db",
                embedding_function=self.embeddings
            )
            self.retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": 4, "score_threshold": 0.5}
            )
            print("✅ 已加载现代化知识库")
            return True
        return False
    
    def retrieve_evidence(self, query: str, top_k: int = 3) -> List[Dict]:
        """现代检索方法 - 支持更多参数"""
        if not self.retriever:
            raise ValueError("请先构建或加载知识库")
        
        # 动态调整检索数量
        if top_k != self.retriever.search_kwargs.get("k", 4):
            self.retriever.search_kwargs["k"] = top_k
        
        # 执行检索
        docs = self.retriever.invoke(query)
        
        # 更丰富的结果格式
        results = []
        for i, doc in enumerate(docs):
            # 计算显示长度（智能截断）
            content = doc.page_content
            if len(content) > 350:
                # 在句号处截断，保持完整性
                truncate_point = content[:350].rfind('。')
                if truncate_point > 200:
                    content = content[:truncate_point+1] + "..."
                else:
                    content = content[:300] + "..."
            
            results.append({
                "rank": i + 1,
                "content": content,
                "source": Path(doc.metadata.get("source", "未知")).name,
                "page": doc.metadata.get("page", 0),
                "relevance_score": float(doc.metadata.get("score", 0.0))
            })
        
        return results
    
    def create_retrieval_chain(self):
        """创建现代LCEL检索链"""
        if not self.retriever:
            raise ValueError("请先构建或加载知识库")
        
        # 更优雅的LCEL链
        retrieval_chain = (
            RunnablePassthrough()
            | (lambda x: x["query"])  # 提取查询
            | self.retriever  # 直接使用检索器
            | (lambda docs: [
                {
                    "content": doc.page_content[:300] + ("..." if len(doc.page_content) > 300 else ""),
                    "source": doc.metadata.get("source", "未知")
                }
                for doc in docs
            ])
        )
        
        return retrieval_chain
    
    def similarity_search_with_score(self, query: str, k: int = 3):
        """带相似度分数的搜索（直接向量库操作）"""
        if not self.vectorstore:
            raise ValueError("向量库未初始化")
        
        return self.vectorstore.similarity_search_with_score(query, k=k)

# 现代化的测试函数
def test_modern_retriever():
    """测试现代检索器"""
    import time
    
    print("🧪 测试现代化证据检索器")
    print("=" * 50)
    
    retriever = ModernEvidenceRetriever()
    
    start_time = time.time()
    
    # 尝试加载现有知识库
    if not retriever.load_existing_knowledge_base():
        print("构建新的现代化知识库...")
        if not retriever.build_knowledge_base():
            return
    
    load_time = time.time() - start_time
    print(f"⏱️  加载时间: {load_time:.2f}秒")
    
    # 测试查询
    test_queries = [
        {"query": "洋葱能杀死感冒病毒吗？", "k": 3},
        {"query": "如何科学预防感冒？", "k": 2},
        {"query": "隔夜水真的致癌吗？", "k": 3}
    ]
    
    for test in test_queries:
        print(f"\n🔍 查询: {test['query']}")
        print("-" * 40)
        
        results = retriever.retrieve_evidence(test['query'], top_k=test['k'])
        
        if not results:
            print("   未找到相关证据")
            continue
        
        for r in results:
            print(f"   [{r['rank']}] 相关度: {r['relevance_score']:.3f}")
            print(f"      内容: {r['content']}")
            print(f"      来源: {r['source']}")
    
    # 演示直接向量搜索（高级功能）
    print("\n🎯 高级功能: 带分数的相似度搜索")
    query = "洋葱和感冒的关系"
    results_with_scores = retriever.similarity_search_with_score(query, k=2)
    
    for i, (doc, score) in enumerate(results_with_scores):
        print(f"   结果{i+1} [分数: {score:.3f}]: {doc.page_content[:150]}...")

if __name__ == "__main__":
    test_modern_retriever()