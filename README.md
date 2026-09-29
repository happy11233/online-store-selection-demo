# 线上商店选品 Demo

AIMID 是一个面向图文带货场景的本地选品工作台：从热点观察、商品筛选和内容建议，到投放回流与模型迭代快照，提供一条可演示、可复盘的业务链路。

**数据边界：**项目只读取仓库内的模拟商品、热点和投放数据，不爬取抖音，也不调用抖音真实 API。正式接入入口展示审批条件，但在本地模式下不会发起平台请求。可选的千问模型服务与抖音数据源是两套独立配置。

## 功能

- **热点趋势：**按时间和类目查看热点、热度变化，并把选中的热点带入选品工作台。
- **AI 选品：**清洗商品数据，按佣金、评分、退货率等规则初筛，再计算商品潜力、热点语义匹配和图文场景匹配分；展示过滤原因与内容选题。
- **内容与回流：**生成图文草稿，记录模拟曝光、点击、成交、退款，按事件 ID 去重，并生成训练数据快照。
- **管理台：**管理员、运营、观察员三级权限；管理员可维护账号、规则阈值和模拟数据源同步。推荐结果可导出 CSV。

默认使用可解释的离线推理，因此不需要模型密钥也能运行完整流程。当前潜力分和评估指标用于演示，**不是**基于真实投放样本训练的转化率预测模型。

## 本地运行

环境：Python 3.10+、Node.js 18+。

~~~bash
# 后端，终端 A
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
LLM_PROVIDER=demo uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 前端，终端 B
cd frontend
npm install
npm run dev
~~~

打开 http://localhost:5173。首次访问时创建本机管理员账号，密码至少 12 位。FastAPI 文档位于 http://127.0.0.1:8000/docs。

前端默认请求与页面同名主机的 8000 端口；端口不同时可设置 VITE_API_BASE_URL。项目根目录的 .env 可选，内容可参考 .env.example。**不要提交 .env、真实密钥或本机运行数据。**

如需试用本地 Qwen 或阿里百炼，可按 .env.example 配置 LLM_PROVIDER 和对应模型参数。千问服务不可用时，推理会回退到离线逻辑；使用云模型可能产生调用费用。抖音平台凭证不应填入这些模型变量。

## 页面与权限

| 页面 | 路径 | 主要操作 |
| --- | --- | --- |
| 选品工作台 | /workspace | 配置阈值、运行推荐、查看解释与内容草稿、导出 CSV |
| 热点趋势 | /hotspots | 浏览模拟热度历史，选择热点进入选品 |
| 投放回流 | /feedback | 提交模拟投放数据，查看漏斗和训练快照 |
| 数据源接入 | /sources | 分别连接、同步商品和热点模拟数据；查看正式接入条件 |
| 账号与权限 | /users | 管理员创建系统账号 |

| 角色 | 查看业务数据 | 选品、回流、导出 | 规则、模拟同步、账号管理 |
| --- | --- | --- | --- |
| 观察员 | ✓ | — | — |
| 运营 | ✓ | ✓ | — |
| 管理员 | ✓ | ✓ | ✓ |

系统登录与抖音平台授权互不相同。系统密码采用 Argon2 哈希；本地会话存于 SQLite，使用可撤销的 HttpOnly Cookie 和 CSRF 校验。首次管理员初始化仅允许本机请求。浏览器刷新后可恢复有效会话，退出登录会撤销当前会话。

## 实现结构

| 目录 | 职责 |
| --- | --- |
| backend/app/ai/ | 商品清洗与特征、潜力评分、语义匹配、多模态简化匹配、推荐流水线 |
| backend/app/integrations/ | 模拟数据源同步与持久化端口；正式抖音客户端仅定义接口 |
| backend/app/main.py、auth.py、services.py | HTTP 契约、系统鉴权与业务编排 |
| backend/data/ | 模拟种子数据；运行快照和账号数据库被 Git 忽略 |
| frontend/src/ | React 页面、HTTP 客户端与管理台组件 |
| docs/architecture.mmd | Mermaid 架构图 |

当前后端使用 FastAPI；本地数据存储为 JSON 和 SQLite。生产目标中的 MySQL、Redis、APScheduler、LightGBM 训练和获批的平台适配器尚未接入，不应把本地结果当成线上指标。职责上，AI 模块处理特征、排序与内容生成；后端负责数据接入、鉴权和存储；前端负责操作与结果展示。

## 接口概览

- /api/auth/*：系统账号初始化、登录、当前用户、退出与管理员创建账号。
- /api/data-sources：模拟商品、热点数据源状态；连接和同步需要管理员权限。
- /api/integrations/douyin/*：正式接入状态与受限入口；本地授权和真实同步请求明确拒绝。
- /api/hotspots、/api/products、/api/rules：热点、商品和筛选规则。
- /api/recommendations、/api/content-drafts、/api/recommendations/export：推荐、内容草稿和 CSV 导出。
- /api/feedback、/api/loop/*：投放回流、指标与训练快照。

数据源同步会校验必需字段和数值范围，拒绝重复或异常记录，以原子写入方式保存快照，并标注 mock 来源；它不会凭空补齐缺失字段。正式接入时，商品和热点权限需分别确认，经官方应用与账号授权后由后端实现对应适配器。

## 验证

~~~bash
# 首次运行浏览器测试时
cd frontend && npx playwright install chromium

# 从项目根目录运行完整检查
./scripts/check_demo.sh
~~~

检查脚本依次运行后端契约测试、Python 编译检查、前端构建和 Playwright 桌面/移动端流程。浏览器测试使用独立临时数据目录和离线模型，不修改日常演示数据。

面试演示与模型选择说明见 [项目演示备忘](docs/interview-guide.md)。
