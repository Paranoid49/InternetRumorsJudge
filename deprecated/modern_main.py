# modern_main.py - 使用现代组件的主程序
from query_parser import build_chain
from modern_retriever import ModernEvidenceRetriever
from typing import Dict, Any


class ModernRumorVerificationSystem:
    """现代化谣言鉴定系统"""

    def __init__(self):
        print("🚀 初始化现代化谣言鉴定系统...")

        # 1. 查询解析器（已现代化）
        self.query_parser = build_chain()

        # 2. 现代证据检索器
        self.retriever = ModernEvidenceRetriever()
        if not self.retriever.load_existing_knowledge_base():
            print("构建现代化知识库...")
            self.retriever.build_knowledge_base()

        # 3. 创建现代LCEL工作流
        self.retrieval_chain = self.retriever.create_retrieval_chain()

        print("✅ 系统初始化完成\n")

    def verify(self, user_input: str) -> Dict[str, Any]:
        """现代化的验证流程"""
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console()

        # 步骤1: 解析查询
        with console.status("[bold blue]解析查询中...") as status:
            try:
                parsed = self.query_parser.invoke({"query": user_input})
                status.update(f"[bold green]解析完成: {parsed['entity']}")
            except Exception as e:
                console.print(f"[red]❌ 解析失败: {e}")
                return None

        # 步骤2: 检索证据
        search_query = f"{parsed['entity']} {parsed['claim']}"

        with console.status(f"[bold blue]检索证据: {search_query}...") as status:
            try:
                evidence = self.retriever.retrieve_evidence(search_query)
                status.update(f"[bold green]找到 {len(evidence)} 条证据")
            except Exception as e:
                console.print(f"[red]❌ 检索失败: {e}")
                return None

        # 现代化输出显示
        console.print(Panel.fit(
            f"[bold cyan]🧪 核查完成[/bold cyan]\n"
            f"[yellow]输入:[/yellow] {user_input}\n"
            f"[yellow]实体:[/yellow] {parsed['entity']}\n"
            f"[yellow]主张:[/yellow] {parsed['claim']}\n"
            f"[yellow]分类:[/yellow] {parsed['category']}",
            title="核查报告",
            border_style="cyan"
        ))

        if evidence:
            table = Table(title="🔍 相关证据", show_header=True, header_style="bold magenta")
            table.add_column("排名", style="dim", width=6)
            table.add_column("相关性", width=8)
            table.add_column("内容", width=60)
            table.add_column("来源", style="dim", width=20)

            for e in evidence:
                relevance = "🟢" if e["relevance_score"] > 0.7 else "🟡" if e["relevance_score"] > 0.4 else "🔴"
                table.add_row(
                    str(e["rank"]),
                    f"{relevance} {e['relevance_score']:.3f}",
                    e["content"],
                    e["source"]
                )

            console.print(table)
        else:
            console.print("[yellow]⚠️  未找到相关证据[/yellow]")

        return {
            "parsed": parsed,
            "evidence": evidence,
            "search_query": search_query
        }


def main():
    """主函数"""
    system = ModernRumorVerificationSystem()

    # 测试案例
    test_cases = [
        "吃洋葱能杀死感冒病毒",
        "晚上吃姜等于吃砒霜",
        "喝隔夜水会致癌",
    ]

    for test in test_cases:
        system.verify(test)
        print("\n" + "=" * 80 + "\n")

    # 交互模式
    print("💬 现代化交互模式 (输入 'quit' 退出)")
    while True:
        try:
            user_input = input("\n请输入要核查的谣言: ").strip()
            if user_input.lower() in ['quit', 'exit', '退出', 'q']:
                print("👋 再见！")
                break
            if user_input:
                system.verify(user_input)
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


if __name__ == "__main__":
    # 安装 rich 库获得更好显示效果: pip install rich
    main()