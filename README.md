# 钻具卡钻及钻具失效处置方案生成系统

本项目面向钻井、修井及井下复杂事故处置场景，建设一套能够针对**钻具卡钻**和**钻具失效**两类故障生成处置方案的智能化系统。系统基于行业标准、事故案例和工程处置流程，对用户输入的事故描述进行解析、匹配、推理、审核和归档，输出可执行、可追溯、可复核的处置建议。

## 一、建设目标

系统围绕两类核心故障开展建设：

1. **钻具卡钻类故障**
   - 支持识别砂卡、键槽卡、压差卡、缩径卡、井壁垮塌卡等典型场景。
   - 支持生成循环洗井、解卡剂浸泡、活动钻具、震击解卡、打捞、套铣、磨铣等分阶段处置建议。

2. **钻具失效类故障**
   - 支持识别钻杆断裂、接头失效、扣型损伤、疲劳断裂、落鱼不明等典型场景。
   - 支持生成鱼顶确认、工具选择、打捞路径、修整鱼顶、套铣处理和后续作业建议。

系统输出内容包括事故概况、关键信息缺失、相似案例、分阶段处置方案、工具清单、判断节点、应急预案、引用依据和风险提示。

## 二、主要功能

- **知识库构建**：将行业标准、事故案例和综合分析资料整理为结构化 Wiki。
- **事故解析**：从自然语言事故描述中提取井型、井深、鱼顶深度、落鱼类型、井液密度、井斜角、扣型等字段。
- **故障识别**：判断事故属于钻具卡钻、钻具失效或复合场景。
- **案例匹配**：从历史案例中匹配相似事故，提炼可借鉴经验和风险注意事项。
- **方案生成**：生成激进方案、保守方案和最终综合处置建议。
- **合规审核**：对工具选型、作业流程、升级条件和高风险动作进行校核。
- **引用追溯**：区分标准依据、案例依据和工程推断。
- **结果归档**：将最终方案保存为 Markdown 文件，便于查看、导出和留痕。
- **Web 前端**：提供类似问答工作台的使用入口，展示事故解析、方案过程、引用依据和风险提示。

## 三、知识库内容

当前 Wiki 知识库包含：

- 3 个标准知识页
  - `wiki/standards/打捞工具目录.md`
  - `wiki/standards/解卡操作规程.md`
  - `wiki/standards/水平井特殊工艺.md`
- 15 个事故案例页
  - `wiki/cases/案例01_长庆油田SH一108井.md`
  - `wiki/cases/案例02_华北油田LG一4井.md`
  - `wiki/cases/案例03_大港油田_GSH-23-1井.md`
  - `wiki/cases/案例04_华北油田G一13井.md`
  - `wiki/cases/案例05_华北油田Z-86-1井.md`
  - `wiki/cases/案例06_胜利油田SC一1井.md`
  - `wiki/cases/案例07_长庆油田SH一93井.md`
  - `wiki/cases/案例08_华北油田J-20井.md`
  - `wiki/cases/案例09_长庆油田SH一75井.md`
  - `wiki/cases/案例10_河南油田T一487井.md`
  - `wiki/cases/案例11_胜利油田C一119井.md`
  - `wiki/cases/案例12_胜利油田G一3井.md`
  - `wiki/cases/案例13_塔里木油田LN一33井.md`
  - `wiki/cases/案例14_华北油田Y-29-2井.md`
  - `wiki/cases/案例15_辽河油田SH125井.md`
- 3 个综合分析页
  - `wiki/synthesis/工具选型决策树.md`
  - `wiki/synthesis/风险评估矩阵.md`
  - `wiki/synthesis/常见失败原因.md`
- 案例清单
  - `wiki/cases/case_manifest.json`

生成方案保存在 `wiki/generated_plans/` 和 `outputs/` 下。生成方案用于结果归档，不会自动混入真实案例库。

## 四、目录结构

```text
.
├── reference/                  # 原始 PDF 资料
├── data/raw_markdown/          # PDF 解析后的中间 Markdown
├── wiki/                       # 结构化知识库
│   ├── standards/              # 标准知识页
│   ├── cases/                  # 事故案例页
│   ├── synthesis/              # 综合分析页
│   └── generated_plans/        # 模型生成方案归档
├── src/                        # 后端、Agent 和 Wiki 构建代码
│   ├── agents/                 # 事故解析、案例匹配、方案生成、合规审核等 Agent
│   └── wiki_builder/           # PDF 解析、Wiki 构建、健康检查和图谱构建
├── frontend/                   # React + TypeScript 前端
├── outputs/                    # 最终方案、研发计划等输出材料
├── graph/                      # Wiki 链接图输出
├── requirements.txt            # Python 依赖
└── .env.example                # 环境变量示例
```

## 五、运行方式

### 1. 后端环境

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中配置模型服务密钥和知识库路径。

### 2. Wiki 构建与检查

```bash
python src/main.py --mode build
python src/wiki_builder/health.py
python src/wiki_builder/graph_builder.py
```

### 3. 命令行求解

```bash
python src/main.py --mode solve --description "现场事故描述..."
```

### 4. 命令行查询

```bash
python src/main.py --mode query --question "水平井卡钻后应如何处理？"
```

### 5. 启动后端服务

```bash
uvicorn src.web_api:app --host 0.0.0.0 --port 8000
```

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端启动后，可在浏览器中访问 Vite 输出的本地地址。

## 六、Web API

后端主要接口包括：

```text
GET  /api/health
GET  /api/sessions
POST /api/sessions
POST /api/solve
GET  /api/outputs/{id}
GET  /api/wiki/pages
GET  /api/wiki/pages/{path}
GET  /api/wiki/search?q=...
```

## 七、研发计划

项目研发计划已整理为 Markdown 文件：

```text
outputs/研发计划/钻具卡钻及钻具失效处置方案生成系统研发计划.md
```

计划周期为 2026 年 5 月 15 日至 2026 年 9 月 15 日，覆盖项目启动、架构设计、知识库建设、模块开发、前后端联调、试验验证和最终验收。

## 八、注意事项

1. `reference/` 中的原始 PDF 作为只读资料使用。
2. `.env` 文件包含本地密钥配置，不提交到代码仓库。
3. 生成方案只进入 `outputs/` 或 `wiki/generated_plans/`，不自动写入 `wiki/cases/`。
4. 对无标准条款或案例支撑的建议，应明确标注为工程推断。
5. 系统不得输出无依据的精确扭矩、拉力、震击参数等工程参数。

