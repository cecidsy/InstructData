# InstructData ChatBI

WHU Cecilia Deng · 个人项目探索

本项目是用python和大模型进行自然语言数据分析的探索。上传 Excel 或连接数据库后，可以用中文问数、画图，也可以清理 Excel 并下载结果。通过调用大模型把问题转成分析计划，程序检查涉及的字段和操作，再用 pandas 计算。

## 快速开始

克隆仓库后，用下面的命令创建本机的 `.venv`，再从 `requirements.txt` 安装依赖。提交到 GitHub 时，`.gitignore` 会排除 `.venv/`，依赖清单 `requirements.txt` 随源码提交。

推荐使用 Python 3.12。从项目根目录运行以下命令。

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

**macOS / Linux**

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

打开 [本地应用](http://127.0.0.1:8501)，在侧栏 **大模型设置** 填写与 Chat Completions 兼容的完整接口 URL、模型名称和 API 密钥，然后点击 **保存模型设置**。配置写入本机的 `.streamlit/model-settings.json`，下次启动会自动读取。密钥以明文保存在该文件中，文件已加入 `.gitignore`。接口和模型名称不变时，密钥留空会沿用已有密钥。

**模型配置优先级**

1. **本地文件优先。** 如果 `.streamlit/model-settings.json` 存在且有效，应用使用文件中的整套配置，即使环境变量也已设置。文件里的 API 密钥为空时，仍按空密钥运行。
2. **文件缺失时读取环境变量。** 启动前设置 `INSTRUCTDATA_MODEL_URL` 和 `INSTRUCTDATA_MODEL`，需要认证时再设置 `INSTRUCTDATA_MODEL_API_KEY`。已有本地文件时，删除它即可切回环境变量。

两种方式可以同时配置。应用按上述顺序选择一套。如果本地文件存在但无法读取或格式有误，页面会提示检查文件或重新保存。

**阿里云百炼（北京）配置示例**

| 页面字段 | 填写内容 |
| --- | --- |
| 对话接口 URL | `https://<业务空间ID>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions` |
| 模型 ID | 例如 `qwen4-max`。使用百炼控制台提供的 API 模型 ID，并保留大小写。 |
| API 密钥 | 使用与目标地域和业务空间匹配的百炼密钥。 |

将 `<业务空间ID>` 替换为控制台中的实际 ID。百炼文档里的 SDK 基础地址通常以 `/compatible-mode/v1` 结尾，本项目需要包含 `/chat/completions` 的完整 HTTP 地址。如遇 HTTP 404，先核对路径和模型 ID，再检查模型是否在该业务空间开通。 [百炼 Chat 接口](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions) · [Qwen4-Max 模型 ID](https://help.aliyun.com/zh/model-studio/qwen4-max)

## 演示

启动应用、配置模型并准备好样例数据后，在网页上完成下面四步约需三分钟。保持应用终端运行，另开一个终端，在项目根目录执行以下命令。终端会打印 `sales.xlsx` 和 `sales.db` 的完整路径，两份文件的数据相同。

```powershell
.\.venv\Scripts\python.exe scripts/create_demo.py
```

macOS 或 Linux 使用 `.venv/bin/python scripts/create_demo.py`。

1. **问数。** 在网页侧栏上传打印路径中的 `sales.xlsx`，选择 `sales` 工作表，在页面底部输入「这张表有什么数据？」。在聊天区核对 **3 行、2 列**，字段是 `region`（地区）和 `amount`（金额）。
2. **绘图。** 输入「各地区销售额一共多少？帮我画成柱状图」。在结果表和图表中核对华东 **320**、华南 **80**。可以继续问「把结果改成折线图」。
3. **下载。** 输入「按地区去重，每个地区保留第一条，导出 Excel」。点击回复里的 **下载处理结果 (.xlsx)**，打开下载文件，核对华东 **120**、华南 **80** 各一行。
4. **用数据库复现。** 把侧栏来源切换到 **关系数据库 → SQLite**，粘贴打印出的 `sales.db` 完整路径。点击 **连接并列出数据表**，选择 `sales` 后点击 **读取数据**。重新询问各地区销售额，结果应与步骤 2 一致。

## 功能范围

| 已实现 | 使用范围 |
| --- | --- |
| 数据源 | Excel 支持 `.xlsx`、`.xls`，首行为列名，默认上传上限 20 MB。数据库支持 SQLite、MySQL、PostgreSQL 的单表读取。SQLite 以只读方式打开，远程库建议使用只读账号。 |
| 自然语言问答 | 支持数据概况、记录数、总和、平均值、最值、分组汇总和单条件筛选。可以在同一数据源中追问。 |
| 数据可视化 | 支持柱状图、折线图和散点图。在页面上可展开「查看数据与统计」核对字段和结果。 |
| Excel 处理 | 支持筛选、排序、去重、删空行和填补缺失值。下载文件为新建 `.xlsx`，包含处理后的数据表。原样式、公式和其他工作表不包含在导出中。 |

分析、绘图和导出基于当前工作表或数据库表读取到的最多 10,000 行。切换数据源或工作表会重新开始对话。每条处理指令都以当前选中的原始数据为起点；想接着清理，可重新上传下载的结果。

发给模型的是字段名、字段类型、已读取行数、用户问题和近期分析上下文。表中的数据行和工作簿在本地处理。使用外部模型时，问题里主动写入的内容会随请求发送。

## 功能计划

- 演示使用 Excel 和 SQLite。两种来源共用分析代码，结果可以在「查看数据与统计」中核对。
- MySQL 和 PostgreSQL 适合已有数据库的场景。初版的分析范围是一张表，后续计划添加多表关联以及沙箱、网关等服务，以支持复杂数据分析与多用户并发。

## 目录结构与阅读顺序

```text
InstructData/
├── app.py                     应用启动入口
├── instructdata/              应用代码
├── scripts/                   演示数据生成脚本
├── tests/                     自动测试
├── .streamlit/config.toml     网页监听地址和上传上限
├── .github/workflows/tests.yml GitHub 自动测试配置
├── .gitignore                 Git 忽略规则，例如本地 .venv
├── requirements.txt           Python 依赖清单
└── README.md                  项目与使用说明
```

| 文件 | 职责 |
| --- | --- |
| [app.py](app.py) | Streamlit 启动入口 |
| [instructdata/web.py](instructdata/web.py) | 主页面、数据源配置和数据预览 |
| [instructdata/chat_view.py](instructdata/chat_view.py) | 模型设置、对话、图表与下载 |
| [instructdata/chat.py](instructdata/chat.py) | 请求模型、校验并执行分析计划、导出 Excel |
| [instructdata/sources.py](instructdata/sources.py) | Excel 解析、数据库连接和读表 |
| [instructdata/analysis.py](instructdata/analysis.py) | 字段统计和分组汇总 |
| [instructdata/__init__.py](instructdata/__init__.py) | 标记 `instructdata` 为 Python 包 |
| [scripts/create_demo.py](scripts/create_demo.py) | 生成 Excel 和 SQLite 演示数据 |

从 `app.py` 进入 `web.py` 的 `main()`。选表时读 `sources.py`，提交问题时读 `chat_view.py`。要看模型和计算各做了什么，对照 `chat.py` 中的 `model_plan()` 和 `execute()`。

## 架构与技术

浏览器通过 Streamlit 与本地的 Python 进程交互，页面、数据读取和运算都由这个进程完成。大模型服务通过 HTTP 接入，只负责把问题转成分析计划或返回文字答复。

```text
数据路径   Excel / 数据库 → sources.py → pandas DataFrame
对话路径   浏览器 → chat_view.py → chat.py 请求模型 → JSON 分析计划
结果路径   分析计划 + DataFrame → chat.py 校验并执行 → 回复 / 图表 / Excel
```

例如，问「各地区销售额一共多少」时，模型需要把「地区」对应到 `region`，把「销售额」对应到 `amount`，并返回按地区求和的计划。应用检查字段存在且金额是数值列，再计算出华东 320、华南 80。

| 技术 | 在项目中的用途 |
| --- | --- |
| Python、Streamlit | 运行应用，提供网页、侧栏、会话状态、聊天输入和图表 |
| pandas | 用 DataFrame 表示读入的表格，执行筛选、分组和统计 |
| SQLAlchemy | 统一读取关系数据库。SQLite 使用 Python 自带的 `sqlite3`，MySQL 使用 PyMySQL，PostgreSQL 使用 Psycopg |
| openpyxl、xlrd | openpyxl 读写 `.xlsx`，xlrd 读取旧版 `.xls` |
| HTTP、JSON | 请求 Chat Completions 兼容模型接口并解析分析计划 |
| unittest、GitHub Actions | 本地运行测试，在 GitHub 上自动复跑 |

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS 或 Linux 将命令中的 Python 路径替换为 `.venv/bin/python`。[测试](tests/)覆盖模型请求与分析计划、Excel 读写、SQLite 只读连接和页面交互，[GitHub Actions](.github/workflows/tests.yml) 使用同一套测试。自动测试使用模拟模型响应，演示前需用自己的接口验证模型效果。
