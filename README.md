# AI 商品导购 Agent

当前已完成 Agent V2：React 前端仍可使用，FastAPI 后端通过 Agent Loop、Tool Registry、受控知识库和最终事实校验执行商品导购。

## 目录

```text
project/
├─ frontend/
├─ backend/
│  ├─ app/main.py
│  ├─ app/api/
│  ├─ app/agent/
│  ├─ app/rules/
│  ├─ app/tools/
│  ├─ app/data/
│  └─ tests/
├─ .env.example
└─ README.md
```

## 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：<http://127.0.0.1:8000>

健康检查：<http://127.0.0.1:8000/api/v1/health>

Swagger：<http://127.0.0.1:8000/docs>

## 启动前端

```powershell
cd frontend
npm install
npm run dev
```

如果使用 pnpm，可改为 `pnpm install` 和 `pnpm run dev`。

前端地址：<http://localhost:5173>

前端默认调用 `http://127.0.0.1:8000`，可通过 `frontend/.env.local` 中的 `VITE_API_BASE_URL` 修改。

## 当前已实现

- React + Vite + TypeScript 聊天页面骨架
- FastAPI 服务和 CORS
- `GET /api/v1/health`
- `POST /api/v1/chat` 标准 JSON Agent 接口
- Swagger `/docs`
- 前端真实调用后端接口
- 内存会话状态：预算、偏好、排除项、关注点和候选 SKU
- Agent V2 Tool Calling Loop：DeepSeek → 工具 → 工具结果 → DeepSeek
- 工具调用上限、重复调用检测、超时和异常降级
- `used_tools`、`needs_confirmation` 和候选商品事实回传前端
- MOCK_LLM 模式：未配置模型 Key 时仍可完成闭环
- JSON 商品、价格和政策知识库
- 安全、预算、排除项和事实校验
- 7 类核心场景的自动化测试

## Agent V2 测试

```powershell
cd backend
pytest -q
```

商品事实位于 `backend/app/data/products.json` 和 `prices.json`；政策边界位于 `policies.json`。默认 `.env.example` 中 `MOCK_LLM=true`，因此没有 LLM API Key 也能启动。

Agent Loop 参数可通过环境变量调整：`AGENT_MAX_STEPS`、`AGENT_MAX_TOOL_CALLS`、`AGENT_TOOL_TIMEOUT`。工具包括 `search_products`、`get_product_detail`、`compare_products`、`get_price`、`get_policy` 和 `get_bundle_options`。

## DeepSeek V4 Flash

复制 `.env.example` 为项目根目录的 `.env`，填入 Key：

```text
MOCK_LLM=false
LLM_API_KEY=你的 DeepSeek API Key
LLM_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

启动后可先访问 `GET /api/v1/llm/status` 查看是否读取到配置（不会返回 Key），再调用 `POST /api/v1/llm/test` 做一次真实连通性测试。推荐接口会调用 DeepSeek 组织推荐文案，但商品名称、规格、价格和安全/预算判断仍由本地代码控制；调用失败时会自动回退到确定性文案。
