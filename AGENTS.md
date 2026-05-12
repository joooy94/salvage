# 钻具落断事故处置系统开发规范

本文档是本仓库的开发指令文件。后续开发、重构、测试、Wiki 构建和 Agent 编排均应遵循本文档。

## 1. 项目目标

构建一个钻具落断事故智能处置系统。系统接收真实事故描述，基于本地 4 份权威文档生成可执行、可追溯、可审核的处置方案。

系统分为两个阶段：

1. 离线阶段：将 PDF 编译为结构化 Markdown Wiki。
2. 在线阶段：使用 LangGraph 编排多个专家 Agent，读取 Wiki、对事故进行分析、辩论、合规审核，并生成最终方案。

核心原则：

1. Wiki 是持久化知识层，不是临时检索缓存。
2. Agent 只能基于 Wiki、用户输入和明确标注的工程推断输出结论。
3. 所有关键建议必须能追溯到标准条款、案例页或综合分析页。
4. 生成方案不得自动混入真实案例库，避免知识污染。

## 2. 只读源文档

当前源文档位于 `reference/`，不得修改原始 PDF。

| 文件 | 类型 | 用途 |
| --- | --- | --- |
| `reference/SY 5069-2017石油天然气工业钻井和采油设备 管柱类落物打捞工具.pdf` | 行业标准 | 管柱类落物打捞工具规格、分类、适用范围 |
| `reference/SY_T 5587.12-2018常规修井作业规程 第12部分：解卡打捞.pdf` | 行业标准 | 常规修井解卡打捞作业规程 |
| `reference/SYT 6987-2024 水平井解卡打捞及冲砂方法.pdf` | 行业标准 | 水平井解卡、打捞、冲砂特殊工艺 |
| `reference/钻具断落事故.pdf` | 案例库 | 15 个真实钻具断落事故案例 |

## 3. 目标目录结构

```text
project_root/
├── AGENTS.md
├── reference/                         # 原始 PDF，只读
├── data/
│   └── raw_markdown/                  # MarkItDown 解析后的中间 Markdown
├── wiki/                              # LLM 编译后的持久化知识库
│   ├── index.md                       # Wiki 总目录
│   ├── overview.md                    # Wiki 总览
│   ├── log.md                         # 构建与维护日志
│   ├── standards/
│   │   ├── 打捞工具目录.md
│   │   ├── 解卡操作规程.md
│   │   └── 水平井特殊工艺.md
│   ├── cases/
│   │   ├── case_manifest.json
│   │   ├── 案例01_XXX井.md
│   │   └── ... 共15个案例
│   ├── tools/                         # 可选：工具实体页
│   ├── procedures/                    # 可选：工艺流程实体页
│   ├── synthesis/
│   │   ├── 工具选型决策树.md
│   │   ├── 风险评估矩阵.md
│   │   └── 常见失败原因.md
│   └── generated_plans/               # 模型生成方案，不与真实案例混放
├── graph/
│   ├── graph.json                     # Wiki 链接图
│   └── graph.html                     # 可选：可视化图
├── src/
│   ├── wiki_builder/
│   │   ├── pdf_parser.py              # MarkItDown PDF -> Markdown
│   │   ├── case_splitter.py           # 自动拆分 15 个案例
│   │   ├── wiki_writer.py             # LLM 编译 Wiki
│   │   ├── health.py                  # 非 LLM 结构健康检查
│   │   ├── lint_wiki.py               # LLM 语义检查
│   │   ├── graph_builder.py           # 构建 Wiki 链接图
│   │   └── build_wiki.py              # 离线构建入口
│   ├── agents/
│   │   ├── accident_parser.py
│   │   ├── case_matcher.py
│   │   ├── aggressive_plan.py
│   │   ├── conservative_plan.py
│   │   ├── compliance_checker.py
│   │   └── decision_maker.py
│   ├── graph.py                       # LangGraph 图定义
│   ├── state.py                       # 共享状态 Schema
│   ├── wiki_loader.py                 # Wiki 加载工具
│   ├── web_api.py                     # Web API 入口
│   └── main.py                        # CLI 入口
├── frontend/                          # GPT 风格问答前端
│   ├── package.json
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── api.ts
│       ├── components/
│       │   ├── Shell.tsx
│       │   ├── Topbar.tsx
│       │   ├── Sidebar.tsx
│       │   ├── ChatThread.tsx
│       │   ├── Composer.tsx
│       │   ├── EvidencePanel.tsx
│       │   ├── AccidentPanel.tsx
│       │   ├── WikiPane.tsx
│       │   └── PlanActions.tsx
│       └── styles.css
├── outputs/                           # 最终处置方案归档
├── requirements.txt
└── .env.example
```

## 4. 技术路线

### 4.1 PDF 解析

使用 Microsoft MarkItDown 作为第一层 PDF 到 Markdown 解析器。

流程：

```text
reference/*.pdf
→ MarkItDown
→ data/raw_markdown/*.md
→ LLM 结构化编译
→ wiki/
```

要求：

1. MarkItDown 输出作为中间文件保存到 `data/raw_markdown/`。
2. 中间 Markdown 不等同于最终 Wiki。
3. 若 MarkItDown 对扫描页、表格或页码解析效果不足，可在 `pdf_parser.py` 中增加备用解析逻辑。
4. 最终 Wiki 页面必须保留来源 PDF、页码、章节或原文摘录。

### 4.2 Wiki 设计

Wiki 参考 llm-wiki 的思想：用 Markdown 页面作为持久化知识层，并通过 `[[wikilinks]]` 维护页面关系。

要求：

1. `wiki/index.md` 覆盖所有页面。
2. `wiki/overview.md` 概述标准、案例和综合结论。
3. `wiki/log.md` 记录每次构建时间、输入文件、生成页面和异常。
4. 页面之间尽量使用 `[[页面名]]` 交叉引用。
5. 标准、案例、工具、工艺和综合分析应互相链接。

### 4.3 LangGraph 在线推理

使用 LangGraph 编排在线处置流程。

节点顺序：

```text
START
  → accident_parser_node
  → case_matcher_node
  → planner_fanout
      → aggressive_plan_node
      → conservative_plan_node
  → compliance_checker_node
  → decision_maker_node
  → output_archiver_node
END
```

第一版可以先在 LangGraph 中串行实现，待输出稳定后再将激进方案和保守方案改为并行分支。

### 4.4 Web 前端

系统需要提供一个类似 GPT 问答页面的 Web 前端，作为主要使用入口。CLI 保留为开发、调试和批处理入口。

前端定位：

1. 面向现场工程师和技术管理人员。
2. 支持自然语言输入事故描述。
3. 以聊天方式展示 Agent 的分析过程和最终处置方案。
4. 同时展示结构化事故信息、相似案例、引用依据和方案归档状态。

推荐技术栈：

1. 后端：`FastAPI`，封装 LangGraph 调用、Wiki 查询和输出归档。
2. 前端：`React + TypeScript + Vite`。
3. 样式：原生 CSS 或轻量组件库，优先保证清晰、稳定、可读。
4. 输出：支持流式显示 Agent 生成过程，至少应支持最终结果一次性返回。

UI 设计应以 `drilling_accident_ui_layout.html` 为基准。该设计稿是本项目的前端视觉与交互约束，不是仅供参考的灵感图。

桌面端骨架：

1. 整体采用固定三栏工作台布局。
2. 顶部栏高度约 44px，左侧显示系统标题与健康状态，右侧显示新建会话与导出按钮。
3. 左侧栏宽度约 220px，用于会话与 Wiki 双标签切换。
4. 中间主栏为聊天区与输入框。
5. 右侧栏宽度约 300px，用于分析依据、结构化信息、置信度和风险提示。
6. 页面整体采用细边框、浅色分区、低装饰性风格，避免营销式视觉。

中间聊天区要求：

1. 用户消息与 Agent 消息区分显示。
2. 每个 Agent 阶段以卡片形式展示，至少包括事故解析、案例匹配、方案生成、合规审核和最终决策。
3. Agent 卡片必须支持显示阶段标签、完成状态和关键摘要。
4. 引用标准或案例时，使用可点击的 citation chip 或引用标签。
5. 点击引用后，应能切换到 Wiki 阅读视图。

右侧依据面板要求：

1. 右侧面板默认显示“分析依据”。
2. 面板分区必须至少包括：事故结构化、方案置信度、引用来源、风险提示。
3. 事故结构化区用字段行展示井型、落鱼类型、鱼顶深度、井液密度、扣型、井斜角等信息。
4. 缺失字段必须以醒目但克制的方式标识。
5. 方案置信度用进度条或百分比展示。
6. 引用来源区应区分标准、案例和工程推断。
7. 风险提示区应使用高/中/低等级提示。

Wiki 阅读视图要求：

1. 点击左侧 Wiki 页面或聊天区引用后，可切换到独立 Wiki 阅读视图。
2. 阅读视图应显示页面标题、来源元信息和正文 Markdown。
3. 右上或左上应有返回按钮回到聊天视图。
4. Wiki 页面正文应支持标题、引用块、列表、表格和链接渲染。
5. 点击引用定位后，应尽量打开对应 Wiki 页面并定位到相关段落或章节。

前端页面结构：

```text
┌─────────────────────────────────────────────────────────────┐
│ 顶部栏：系统名称 / Wiki 健康状态 / 新建会话 / 导出方案       │
├───────────────┬───────────────────────────────┬─────────────┤
│ 左侧导航      │ 中间聊天区                    │ 右侧依据面板 │
│ - 会话        │ - 用户事故描述                │ - 事故结构化 │
│ - Wiki        │ - Agent 分析                  │ - 相似案例   │
│ - 历史方案    │ - 最终处置方案                │ - 引用标准   │
│ - 输出记录    │ - 底部输入框                  │ - 风险提示   │
└───────────────┴───────────────────────────────┴─────────────┘
```

核心交互：

1. 用户在输入框中描述事故，也可以粘贴较长现场记录。
2. 系统先展示结构化事故信息和缺失字段。
3. 中间聊天区依次展示案例匹配、激进方案、保守方案、合规审核和最终方案。
4. 右侧依据面板展示本次使用的 Wiki 页面、标准条款、案例来源和工程推断。
5. 用户可以导出最终方案为 Markdown。
6. 用户可以查看历史生成方案，但历史生成方案不得自动进入真实案例库。
7. 用户可以在左侧 Wiki 标签中浏览、搜索和打开 Wiki 页面。
8. 用户可以在聊天区点击引用并跳转到 Wiki 阅读视图。

左侧导航要求：

1. 左侧包含 `会话` 和 `Wiki` 两个主标签。
2. `会话` 标签展示新建事故、历史会话和已生成方案。
3. `Wiki` 标签展示 Wiki 目录树，包括标准、案例、工具、工艺、综合分析和生成方案。
4. Wiki 目录应支持关键词搜索，至少能按页面标题过滤。
5. 点击 Wiki 页面后，中间区域可切换为 Wiki 阅读视图，或在右侧面板打开引用预览。
6. 从 Agent 输出中的引用点击后，应能定位到对应 Wiki 页面。

前端设计要求：

1. 首屏必须是可用的问答工作台，不做营销式落地页。
2. 布局参考 GPT 问答页面：左侧导航、中间聊天流、底部输入框。
3. 针对本项目增加右侧专业面板，用于显示事故结构化信息、证据和风险。
4. 文案应克制、工程化，不使用装饰性大段说明。
5. 移动端可隐藏左侧导航和右侧依据面板，通过按钮抽屉打开。
6. 最终方案中的表格、标题、引用依据必须有良好 Markdown 渲染效果。
7. 缺失信息、低置信度、无标准依据的工程推断要有醒目标记。

## 5. Wiki 页面规范

### 5.1 标准页面

每个标准页面必须包含元数据和依据块。

```markdown
---
title: 解卡操作规程
source_pdf: SY_T 5587.12-2018常规修井作业规程 第12部分：解卡打捞.pdf
doc_type: standard
extracted_at: YYYY-MM-DD HH:mm:ss
---

## 适用范围

## 关键术语

## 工具与适用条件

## 操作流程

### 条款 X.X
> 来源：SY_T 5587.12-2018，第 N 页，第 X.X 条
> 原文摘录：...

提炼说明：...

## 注意事项与禁忌

## 相关页面
- [[工具选型决策树]]
```

### 5.2 案例页面

`钻具断落事故.pdf` 明确包含 15 个真实案例，必须自动拆成 15 个案例页。

```markdown
---
title: 案例01_XXX井钻具断落事故
source_pdf: 钻具断落事故.pdf
doc_type: case
case_no: 01
source_pages: [N, N+1]
split_confidence: 0.95
---

## 基本信息
- 井名/井型：
- 事故发生层位/深度：
- 钻具组合：
- 落鱼描述：
- 事故原因：

## 井况条件
- 井斜/方位：
- 钻井液类型及性能：
- 地层特征：

## 处置过程

## 使用工具

## 处置结果
- 最终结果：
- 耗时：
- 关键经验：

## 失败教训

## 相关页面
```

### 5.3 案例 Manifest

自动拆分案例时必须生成 `wiki/cases/case_manifest.json`。

```json
[
  {
    "case_no": "01",
    "title": "XXX井钻具断落事故",
    "source_pdf": "钻具断落事故.pdf",
    "source_pages": [3, 4, 5],
    "start_marker": "案例一 ...",
    "end_marker": "案例二 ...",
    "confidence": 0.94,
    "wiki_file": "wiki/cases/案例01_XXX井.md"
  }
]
```

要求：

1. manifest 必须正好 15 条。
2. 每条必须有标题、页码范围、起止标记、置信度和 Wiki 文件路径。
3. 置信度低于 0.8 的案例必须在 `wiki/log.md` 中标记为需要人工复核。

## 6. Wiki 运维命令

后续 CLI 应支持：

```bash
python src/main.py --mode build
python src/main.py --mode solve
python src/main.py --mode query --question "水平井中卡钻后，若套铣失败，下一步应该怎么做？"
python src/wiki_builder/health.py
python src/wiki_builder/lint_wiki.py
python src/wiki_builder/graph_builder.py
```

后续 Web API 应支持：

```text
GET  /api/health                  # Wiki 和服务健康状态
GET  /api/sessions                # 历史会话/方案列表
POST /api/sessions                # 新建事故会话
POST /api/solve                   # 提交事故描述，运行 LangGraph
GET  /api/outputs/{id}            # 查看已归档方案
GET  /api/wiki/pages              # Wiki 页面列表
GET  /api/wiki/pages/{path}       # 查看 Wiki 页面内容
GET  /api/wiki/search?q=...       # 搜索 Wiki 页面
```

如实现流式输出，优先使用：

```text
POST /api/solve/stream            # SSE 流式返回 Agent 过程和最终方案
```

### 6.1 Health

`health.py` 是零 LLM 调用的结构检查。

必须检查：

1. `wiki/index.md`、`wiki/overview.md`、`wiki/log.md` 是否存在。
2. `wiki/standards/` 是否有 3 个标准页。
3. `wiki/cases/` 是否有 15 个案例页。
4. `case_manifest.json` 是否正好 15 条。
5. manifest 指向的 Wiki 文件是否存在。
6. Wiki 页面是否存在空文件。
7. `[[wikilinks]]` 是否有明显断链。

### 6.2 Lint

`lint_wiki.py` 可调用 LLM 做语义检查。

检查内容：

1. 标准页是否缺少来源页码或条款。
2. 案例页是否缺少基本信息、处置过程或结果。
3. 不同页面对同一工具或工艺是否有明显冲突。
4. 案例中出现但没有工具页或相关链接的工具名称。
5. 综合分析页是否引用了不存在的案例或条款。

### 6.3 Graph

`graph_builder.py` 解析 `[[wikilinks]]`，生成：

```text
graph/graph.json
graph/graph.html
```

用途：

1. 查看标准、工具、案例、工艺之间的引用关系。
2. 发现孤立页面。
3. 识别高频工具、高频风险和核心条款。

## 7. Agent 状态设计

`src/state.py` 应定义以下结构。

```python
from typing import TypedDict, List, Dict, Optional

class AccidentInput(TypedDict, total=False):
    raw_description: str
    well_type: str
    depth: float
    fish_type: str
    fish_description: str
    mud_type: str
    additional_info: str
    missing_fields: List[str]

class EvidenceItem(TypedDict):
    source_type: str       # standard/case/synthesis/inference
    source_page: str       # Wiki 页面路径
    source_pdf: str
    page_no: Optional[int]
    clause: Optional[str]
    quote: str
    summary: str

class AgentState(TypedDict, total=False):
    accident: AccidentInput
    evidence: List[EvidenceItem]
    similar_cases: str
    aggressive_plan: str
    conservative_plan: str
    compliance_report: str
    final_plan: str
    debate_rounds: List[Dict]
    wiki_pages_used: List[str]
    confidence_score: float
    output_path: str
```

## 8. Agent 职责

### 8.1 accident_parser

职责：

1. 从用户自然语言中抽取井型、深度、落鱼类型、鱼顶状态、井下复杂情况、已采取措施。
2. 标注缺失字段。
3. 输出结构化 `AccidentInput`。
4. 对关键缺失信息给出影响说明。

### 8.2 case_matcher

职责：

1. 从 15 个案例中匹配最相似的 2-3 个案例。
2. 比较井型、深度、落鱼类型、井况、处置路径。
3. 提炼成功经验和失败教训。
4. 明确哪些经验可以借鉴，哪些不能直接套用。

### 8.3 aggressive_plan

职责：

1. 以尽快恢复钻进和降低停工时间为优先目标。
2. 推荐积极但合规的处置路径。
3. 给出工具、步骤、判断点和失败后转入条件。

约束：

1. 不得凭空给出扭矩、拉力、震击参数。
2. 若标准或案例未给出具体参数，应写“需结合钻具强度、井况和现场设计确认”。
3. 每个关键动作必须引用标准、案例或标记为工程推断。

### 8.4 conservative_plan

职责：

1. 以井控安全、井筒完整和防止事故扩大为优先目标。
2. 采用由轻到重的阶梯式处置。
3. 明确每个阶段的停止条件和升级条件。

典型路径：

```text
井况复核
→ 循环洗井/冲砂
→ 泡解卡剂或浸泡
→ 震击解卡
→ 打捞
→ 套铣/磨铣
→ 侧钻或弃鱼
```

### 8.5 compliance_checker

职责：

1. 审核激进方案和保守方案。
2. 检查工具选型是否符合 SY 5069-2017。
3. 检查作业程序是否符合 SY/T 5587.12-2018。
4. 若为水平井，检查是否符合 SYT 6987-2024。
5. 标注遗漏、冲突和不确定项。

### 8.6 decision_maker

职责：

1. 综合事故输入、案例经验、两套方案和合规审核。
2. 生成最终可执行处置方案。
3. 给出分阶段行动、判断节点、应急预案、工具清单和参考依据。

最终方案必须包含：

1. 事故概况。
2. 关键不确定信息。
3. 处置策略选择。
4. 分阶段处置方案。
5. 工具清单。
6. 判断节点。
7. 应急预案。
8. 参考依据。
9. 注意事项与风险提示。
10. 生成时间、引用 Wiki 页面、方案置信度。

## 9. 输出与归档

最终方案写入：

```text
outputs/处置方案_YYYYMMDD_HHMMSS.md
wiki/generated_plans/处置方案_YYYYMMDD_HHMMSS.md
```

禁止自动写入：

```text
wiki/cases/
```

只有现场执行结果经人工确认后，才允许将其整理为真实案例并加入 `wiki/cases/`。

## 10. 依赖

`requirements.txt` 应至少包含：

```text
anthropic>=0.40.0
langgraph>=0.2.0
langchain-anthropic>=0.3.0
markitdown[pdf]>=0.1.0
python-dotenv>=1.0.0
pydantic>=2.0.0
rich>=13.0.0
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pymupdf>=1.24.0
rapidocr-onnxruntime>=1.2.3
```

PDF 多为扫描页时，`pdf_parser.py` 必须启用 `PyMuPDF + RapidOCR` fallback；MarkItDown 只作为第一层解析器，不能假设它一定能提取扫描版中文 PDF。

`.env.example` 应包含：

```text
ANTHROPIC_API_KEY=your_key_here
WIKI_BUILDER_MODEL=claude-opus-4-5
AGENT_MODEL=claude-sonnet-4-5
WIKI_DIR=./wiki
REFERENCE_DIR=./reference
OUTPUTS_DIR=./outputs
```

## 11. 开发顺序

按以下顺序推进：

1. 搭建目录结构、依赖文件和 CLI 框架。
2. 实现 MarkItDown PDF 解析，生成 `data/raw_markdown/`。
3. 实现标准 Wiki 生成。
4. 实现案例自动拆分，生成 15 个案例页和 `case_manifest.json`。
5. 实现综合分析页、`index.md`、`overview.md`、`log.md`。
6. 实现 `health.py`，保证 Wiki 结构可检查。
7. 实现 `wiki_loader.py` 和 `state.py`。
8. 实现 6 个 Agent。
9. 实现 LangGraph 图，先串行跑通，再优化并行分支。
10. 实现 `main.py --mode solve` 和 `--mode query`。
11. 实现输出归档。
12. 实现 `web_api.py`，提供健康检查、会话、求解、输出和 Wiki 查询接口。
13. 实现 `frontend/` GPT 风格问答页面，左侧包含会话和 Wiki 双标签。
14. 实现 `lint_wiki.py` 和 `graph_builder.py`。

## 12. 验收标准

Wiki 构建验收：

1. `wiki/standards/` 有 3 个标准页。
2. `wiki/cases/` 有 15 个案例页。
3. `case_manifest.json` 正好 15 条。
4. `wiki/synthesis/` 有工具选型决策树、风险评估矩阵、常见失败原因。
5. 每个关键知识点有来源 PDF、页码、章节或原文摘录。

Agent 输出验收：

1. 每个 Agent 输出必须引用具体 Wiki 页面或明确标注工程推断。
2. 最终方案必须包含工具清单、判断节点、应急预案和参考依据。
3. 合规审核必须覆盖三个行业标准。
4. 缺失现场信息不得被伪装成已知事实。

运维验收：

1. `health.py` 可零 LLM 调用检查结构完整性。
2. `lint_wiki.py` 可检查语义冲突和引用缺失。
3. `graph_builder.py` 可生成 Wiki 链接图。
4. 生成方案不会污染真实案例库。

Web 前端验收：

1. 首屏是问答工作台，包含顶栏、左侧导航、中间聊天区、输入框和右侧依据面板。
2. 左侧导航包含 `会话` 和 `Wiki` 双标签。
3. Wiki 标签可以浏览标准、案例、工具、工艺、综合分析和生成方案。
4. 顶栏必须显示系统标题、健康状态和常用操作按钮。
5. 中间聊天区必须以 Agent 卡片展示事故解析、案例匹配、方案生成、合规审核和最终决策。
6. 右侧依据面板必须至少包含事故结构化、方案置信度、引用来源和风险提示四个分区。
7. 可以提交真实事故描述并展示最终处置方案。
8. 可以展示事故结构化结果、相似案例、引用标准和工程推断。
9. 可以查看历史输出并导出 Markdown。
10. Agent 输出中的引用可以关联到对应 Wiki 页面。
11. 点击引用或 Wiki 页面可切换到 Wiki 阅读视图。
12. 缺失信息、低置信度和无直接标准依据的内容有明显提示。
13. 桌面端和移动端均无明显文字重叠或布局错乱。

## 13. 质量红线

1. 不允许 Agent 编造标准条款。
2. 不允许无来源地给出精确工程参数。
3. 不允许将模型生成方案自动加入真实案例库。
4. 不允许把缺失信息写成确定事实。
5. 不允许最终方案缺少引用依据。
6. 不允许修改 `reference/` 中的原始 PDF。
