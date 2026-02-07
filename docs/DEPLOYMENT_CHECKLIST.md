# 生产部署检查清单

本文档提供互联网谣言粉碎机系统生产环境部署的完整检查清单。

---

## 📋 部署前准备

### 1. 环境检查

- [ ] Python 3.11+ 已安装
- [ ] pip 包管理器可用
- [ ] 至少 2GB 可用内存
- [ ] 至少 5GB 可用磁盘空间
- [ ] 网络连接正常（API调用需要）

### 2. 依赖安装

- [ ] 运行 `pip install -r requirements.txt`
- [ ] 验证关键依赖：
  ```bash
  python -c "import langchain; print('langchain:', langchain.__version__)"
  python -c "import chromadb; print('chromadb:', chromadb.__version__)"
  python -c "import pydantic; print('pydantic:', pydantic.__version__)"
  ```

### 3. 配置验证

- [ ] 设置 `DASHSCOPE_API_KEY` 环境变量
  ```bash
  export DASHSCOPE_API_KEY=your_key_here
  ```

- [ ] （可选）设置 `TAVILY_API_KEY` 环境变量
  ```bash
  export TAVILY_API_KEY=your_key_here
  ```

- [ ] 验证配置：
  ```bash
  python -c "from src import config; print('API Key configured:', bool(config.API_KEY))"
  ```

---

## 🗄️ 数据准备

### 4. 知识库构建

- [ ] 准备知识源文件（`.txt` 格式）到 `data/rumors/` 目录
- [ ] 构建向量知识库：
  ```bash
  python -m src.retrievers.evidence_retriever build --force
  ```
- [ ] 验证向量库创建：
  ```bash
  ls -la storage/vector_db/
  ```

### 5. 存储目录

- [ ] 创建必要的存储目录：
  ```bash
  mkdir -p storage/vector_db
  mkdir -p storage/cache
  mkdir -p storage/semantic_cache
  mkdir -p data/rumors
  mkdir -p data/api_monitor
  ```

---

## 🧪 功能测试

### 6. 基本功能测试

- [ ] 运行单元测试：
  ```bash
  pytest tests/unit/ -v
  ```
  预期：至少 90% 测试通过

- [ ] 运行集成测试：
  ```bash
  pytest tests/integration/ -v
  ```

- [ ] 运行健康检查：
  ```bash
  python -c "from src.core.health_check import get_health_checker; import json; print(json.dumps(get_health_checker().check_all(), indent=2, ensure_ascii=False))"
  ```
  预期：所有检查项状态为 `pass` 或 `warning`

### 7. 端到端测试

- [ ] 测试完整核查流程：
  ```bash
  python scripts/main.py "喝隔夜水会致癌吗？"
  ```
  预期：返回裁决结果

- [ ] 测试缓存功能：
  ```bash
  python scripts/main.py "喝隔夜水会致癌吗？"  # 第二次查询
  ```
  预期：使用缓存，速度更快

- [ ] 测试并发查询（可选）：
  ```bash
  python scripts/test_concurrent_safety.py
  ```

---

## 📊 性能基准

### 8. 性能测试

- [ ] 运行性能基准测试：
  ```bash
  python -m pytest tests/benchmarks/test_performance.py -v
  ```

- [ ] 验证关键指标：
  - 缓存命中率 > 30%
  - 本地检索时间 < 200ms
  - 完整流程时间 < 30s（本地命中）

---

## 🔒 安全检查

### 9. 安全配置

- [ ] API密钥未硬编码在代码中
- [ ] API密钥通过环境变量或密钥管理系统配置
- [ ] 存储目录权限正确设置
- [ ] 日志文件不包含敏感信息

### 10. 依赖安全

- [ ] 运行依赖安全检查：
  ```bash
  pip safety check
  ```
  （可选，需要安装 pip-safety）

---

## 📝 监控配置

### 11. API监控

- [ ] 设置每日预算（可选）：
  ```bash
  export API_DAILY_BUDGET=10.0
  ```

- [ ] 设置token限制（可选）：
  ```bash
  export API_DAILY_TOKEN_LIMIT=100000
  ```

- [ ] 验证监控器工作：
  ```bash
  python -c "from src.observability.api_monitor import get_api_monitor; print(get_api_checker().get_daily_summary())"
  ```

### 12. 日志配置

- [ ] 设置日志级别（可选）：
  ```bash
  export LOG_LEVEL=INFO
  ```

- [ ] 验证日志输出：
  ```bash
  python scripts/main.py "测试查询" 2>&1 | grep "INFO"
  ```

---

## 🚀 部署执行

### 13. 启动服务

**命令行模式**：
```bash
python scripts/main.py "待核查查询"
```

**API服务模式**：
```bash
python -m uvicorn src.services.api_service:app --host 0.0.0.0 --port 8000
```

**Web界面模式**：
```bash
python src/services/web_interface.py
```

### 14. 验证部署

- [ ] 检查服务状态
- [ ] 测试基本查询
- [ ] 检查日志输出
- [ ] 验证监控数据

---

## 📋 部署后验证

### 15. 健康检查

运行完整健康检查并记录结果：

```bash
python -c "
from src.core.health_check import get_health_checker
import json

checker = get_health_checker()
result = checker.check_all()

print('=== 健康检查报告 ===')
print(f'整体状态: {result[\"status\"]}')
print(f'运行时间: {result[\"uptime_seconds\"]:.2f}秒')
print()

for check_name, check_result in result['checks'].items():
    status_icon = '✅' if check_result['status'] == 'pass' else '⚠️' if check_result['status'] == 'warning' else '❌'
    print(f'{status_icon} {check_name}: {check_result[\"status\"]}')
    if 'message' in check_result:
        print(f'   消息: {check_result[\"message\"]}')
"
```

预期输出：
```
=== 健康检查报告 ===
整体状态: healthy
运行时间: X.XX秒

✅ configuration: pass
✅ dependencies: pass
✅ storage: pass
✅ cache: pass
✅ parallelism: pass
✅ api_monitoring: pass
```

### 16. 监控确认

- [ ] API调用正常记录
- [ ] 成本数据正常收集
- [ ] 日志正常输出
- [ ] 缓存正常工作

---

## 🔧 故障排查

### 常见问题

**Q: 向量库构建失败**
```bash
A:
1. 检查 data/rumors/ 目录下是否有 .txt 文件
2. 检查 DASHSCOPE_API_KEY 是否正确配置
3. 检查网络连接
4. 查看详细错误日志
```

**Q: API调用失败**
```bash
A:
1. 验证 API_KEY 环境变量
2. 检查 API 密钥是否有效
3. 检查 API 配额是否用完
4. 验证网络连接
```

**Q: 性能较慢**
```bash
A:
1. 检查是否启用了缓存
2. 验证向量库是否已构建
3. 调整并行度配置
4. 检查系统资源使用
```

---

## 📞 支持信息

**技术支持**：
- 查看文档：`docs/` 目录
- 查看优化日志：`OPTIMIZATION_LOG.md`
- 运行健康检查：`src/core/health_check.py`

**版本信息**：
- 当前版本：v1.0.0
- 最后更新：2026-02-07
- 维护者：Claude (守门员)

---

**检查清单版本**: v1.0.0
**最后更新**: 2026-02-07
