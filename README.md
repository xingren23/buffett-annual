# 巴菲特股东大会资料集（CNBC 归档整理）

把 [buffett.cnbc.com](https://buffett.cnbc.com/) 上的伯克希尔·哈撒韦股东大会内容，按年度整理成本地 Markdown 资料集：

- 每年一个文件夹，位于 `annual_meeting/<年份>/`；
- 每个年度文件夹包含**致股东的一封信**、**上午问答**、**下午问答**；
- 上午／下午各自是「索引 + 问答片段」结构，**一个片段只对应一个问题**；
- 每个片段 = 中文问题 + 要点 + 关键引述 + **中文全文逐段翻译** + 英文原文。

## 想读什么，从哪里进

先打开 **[annual_meeting/index.md](annual_meeting/index.md)**（历年索引），再按需求定位：

| 需求 | 入口 |
|---|---|
| 看有哪些年份、规模多大 | `annual_meeting/index.md` 的年度索引表 |
| 看同一个话题历年怎么讲 | `annual_meeting/index.md` 的跨年度主题索引（一行读九年） |
| 先看这一年发生了什么 | `annual_meeting/<年份>/index.md`（会议信息、快速入口、关键事件、来源与口径） |
| 按主题找某个问题 | `morning/index.md` 或 `afternoon/index.md` 的索引表 |
| 读某个问题的完整问答 | 索引表「片段」列的 `qNN-*.md` |
| 只读中文 | 片段内的「问题 + 回答要点 + 中文全文」 |
| 核对原文措辞 | 同一片段末尾的「英文原文」小节（2024 为 CNBC 官方逐字稿，2025 为实录摘录） |
| 读当年致股东信 | 年度概览的「快速入口」表，或直接开 `shareholder-letter-zh.md` / `shareholder-letter-en.md` |

完整读一遍的顺序建议：历年索引 → 年度概览 → 上／下午索引 → 挑片段。索引里的「主题」列是中文标题，片段文件名是英文 slug（跨系统稳定、可排序），内容以中文为主。

## 仓库结构

```
.
├── annual_meeting/
│   ├── index.md             # 历年索引：年度清单 + 每年中英信件与两场索引的直达链接
│   └── <年份>/              # 成品：年度概览 + 双语信件 + 上午/下午问答
├── data/                    # 输入：年份配置 + 中文内容源（标题/要点/引述/全文译文），build 的输入
│   └── <年份>/              # config.json + morning_zh.json + zh/ + letter_zh/ 等（一年一目录，自包含）
├── _source/<年份>/          # 原始素材：CNBC 页面快照、逐字稿、信件 PDF（只读）
├── dist/                    # 技能分发包 buffett-annual-meeting.zip
└── .workbuddy/skills/buffett-annual-meeting/   # 构建工具（技能形态）
```

数据流是单向的，四层各管一段，改文案不必碰抓取逻辑：

```
_source/  抓取快照（页面 HTML、PDF、外部实录）
   ↓ fetch / extract / letter-extract
_source/<年份>/transcript/chapters.json  +  _source/<年份>/letter/derived/
   ↓ scaffold
data/<年份>/qa_scaffold.json   （中文写作底稿：章节标题、提问者、英文问题、轮次数）
   ↓ 人工/模型写中文
data/<年份>/   （config.json、morning_zh.json、afternoon_zh.json、appendix_zh.json、zh/*.json、letter_zh/*.json）
   ↓ build
annual_meeting/<年份>/   （成品 Markdown）
   ↓ validate
链接、译文轮次、占位符检查
```

## 目录约定

```
annual_meeting/
├── index.md                  # 历年索引：年度 × 资源的链接矩阵（新增年份时补一行）
└── <年份>/
    ├── index.md              # 年度概览 + 快速入口：中英信件、两场索引的直达链接
    ├── shareholder-letter-zh.md  # 致股东信：完整中文译文（按原信分节、分段）
    ├── shareholder-letter-en.md  # 致股东信：英文全文（PDF 断行重排 + 表格化）
    ├── morning/              # 上午场
    │   ├── index.md          # 索引：问答表（序号、主题、时间戳、提问者、要点）
    │   ├── qNN-<slug>.md     # 一个提问一个文件
    │   └── aNN-<slug>.md     # 非提问附件（一季报简报、重大宣布等），不计入问数
    └── afternoon/            # 下午场，结构同上
```

**年度 index.md 是单个年份的总入口**：顶部「快速入口」表把**致股东信中英两个文件**与上午／下午索引一次列全，读者不必逐层点开找。

**片段统一模板**：题头表（场次／时间戳／提问者／CNBC 章节／视频链接／主题标签）→ 问题 → 回答要点 → 关键引述（英文原句 + 中译）→ **中文全文（逐段翻译）** → 英文原文 → 返回索引。

其中「回答要点」是提炼，「中文全文」是完整对话的翻译：译文轮次应与英文原文轮次数严格相等、逐段对应。**翻译遇到异常（译文缺失、含空轮次或轮次数不匹配）时不再中止构建：该页跳过「中文全文」，仅保留英文原文**并打 warn；信件缺段同理，对应段落保留英文原文。

**索引只有一张表**：序号、主题、时间戳、提问者、核心要点、片段链接。CNBC 的章节映射只用于内部切分，不写进成品——读者要的是「按问题找」，不是「按章节找」。

**致股东信拆成两个单语文件**：`shareholder-letter-en.md` 只放英文原文，`shareholder-letter-zh.md` 只放完整中文译文；两文件按原信分节、分段一一对应，各自附有经营利润表与绩效表（绩效表起止年份随信而变：2025 年会上对应 1965–2024，2024 年会上对应 1965–2023，2022 年会上对应 1965–2021；2021 年报信没有季度利润表，那封信就只有绩效表）。

**编号规则**：片段编号 `qNN` 是**该场内**序号；题头「全场第 N 问」是跨场连续编号（上午从 1 起，下午接着上午的总数继续）。附件用 `aNN`，不参与问号计数。

## 数据源：两代页面的差别

CNBC 的年会页面有两代结构，直接决定整理成本：

| 年份 | 页面结构 | 逐字稿 |
|---|---|---|
| **1994–2024** | 每场一个长视频页，内嵌 `chapters[]` 章节数组，**每章自带逐字稿**（带 `WARREN BUFFETT:` 等发言者标签与秒级时间戳） | ✅ 完整，可直接抓取 |
| **2025–2026** | 同样是章节数组，但 `transcript` 字段为空，只有章节标题 | ❌ 无，需外部实录或音频转写 |

抓取方式两代通用：请求视频页时带浏览器 UA，页面内嵌 `window.__c_data`（Apollo 缓存）里就是章节与逐字稿；不带 UA 会被 Akamai 拒绝（`Access Denied`）。两代页面都保留**章节标题与起止秒数**，因此片段切分和时间轴对所有年份都能对齐 CNBC 官方结构。

## 处理流程：只走有官方逐字稿的年份

技能已收敛到 1994–2024 一条路径。2025/2026 页面没有逐字稿，`init`/`prepare` 会直接拒绝；现有 2025 成品已定稿在 `annual_meeting/2025/`，不再随工具链更新。

1. `init`：读 CNBC hub，生成 `data/<year>/config.json` 骨架（两场视频 URL 自动填好）；
2. `prepare`：抓两场视频页与信件 PDF → 解析 `window.__c_data` 的 `chapters`，修 `â€™` 乱码，按发言人合并连续片段为「轮次」→ 抽信件 PDF 分节分段；
3. 看 `prepare` 打印的章节表，把提问章节填进配置（跨章的用 `continuations`，一章多问的用 `splits`，非提问环节用 `appendix`/`non_qa`）；
4. `scaffold`：生成英文提问候选与分批计划，据此逐批写中文问题、要点、引述与逐轮译文；
5. `build`：先 `check` 中文 JSON（字段、轮次、引述逐字一致），再生成全部 Markdown，最后 `validate` 链接与产出。

### 两路的实际产出

各年度的章节数、片段数、附件与特殊处理，见 [annual_meeting/index.md](annual_meeting/index.md) 的年度索引表，以及 `.workbuddy/skills/buffett-annual-meeting/references/quirks.md`。

工具已收敛为项目级技能 `.workbuddy/skills/buffett-annual-meeting/`，入口是 `scripts/buffett.py`。年份差异全部放在 `data/<year>/config.json`，代码不按年份分叉。

**当前范围说明**：`data/<年份>/config.json` 现有 2017–2024 八份，工具链覆盖这八年的重建（2017 起含年报信，2016 财年信）；2025 缺官方逐字稿，成品由旧脚本生成、已定稿在 `annual_meeting/2025/`，不纳入工具链；1994–2016 待做，按 `init → prepare → scaffold → build` 即可，无需改代码。

## 中文内容与数据文件

中文内容与英文数据分离，改文案只动 `data/`，不碰抓取逻辑。**一年一个目录、自包含**：

```
data/
└── <年份>/
    ├── config.json            # 年份配置：URL、章节选择、附件、信件分节、关键事件
    ├── morning_zh.json        # 上午各问的中文标题/问题/要点/引述/标签
    ├── afternoon_zh.json      # 下午各问
    ├── appendix_zh.json       # 非提问附件的中文背景/要点/引述/译文
    ├── qa_scaffold.json       # scaffold 生成的写作底稿（不参与 build）
    ├── zh/*.json              # 问答逐轮中文译文，键为 CNBC 章节号（"30" → 译文数组）
    └── letter_zh/part*.json   # 信件逐段译文，键为段落 ID（"06-012" → 中文）
```

- `data/<年份>/zh/` 按章节号区间可分多个分片文件（如 `m04-09.json`），`build` 会合并读取；
- `data/<年份>/letter_zh/` 统一用 `part*.json` 命名，键为段落 ID；
- 翻译过程的中间文件（`2019_parts/`、`2021_parts/`、`2023_parts/`、`2024_parts/`、`meta_part/`、`2021_theme_cells.json`、`2024_qa_zh_all.json`）已随历史存档清理出库，不参与构建。

## 年份配置：`data/<year>/config.json`

一份配置描述一整年，新增年份就是复制 `assets/year-config.example.json` 后改写为 `data/<year>/config.json`：

| 字段 | 内容 |
|---|---|
| `meeting` | 日期、地点、台上人物、议程、年会主页与两场视频 URL |
| `sessions.*.questions` | 有序的 CNBC 章节号列表，即「哪些章节是提问」；一章多问写 `"12.1"`、`"12.2"` |
| `sessions.*.continuations` | 章节号 → 它延续的那个提问（跨章的提问，后续章节不进 `questions`） |
| `sessions.*.splits` | 章节号 → turn 区间列表（左闭右开，末段可写 `null`），配合 `"12.1"` 这类编号 |
| `sessions.*.appendix` | 章节号 → 输出文件名 + 中文数据键（+ `also` 表示跨多章的一段） |
| `sessions.*.non_qa` | 章节号 → 非提问章节的说明（仅作文档标注，成品索引不再输出章节对照表） |
| `paths` | 中文元数据与译文位置；可整段省略，默认 `data/<year>/morning_zh.json` 等约定路径（一年一目录），仅在偏离约定时才写 |
| `letter` | 来源年度、PDF 文件名、发布日期、分节标题、利润表行、绩效表起止年份与说明 |
| `readme` | 年度概览的关键事件、方法、来源、已知缺陷 |

**凡是随年份变化的文字都不写进 Python**，一律进配置或中文 JSON。

## 构建与校验

依赖 Python 3.10+ 与 `pypdf`（`pip install -r .workbuddy/skills/buffett-annual-meeting/scripts/requirements.txt`）。若报 `ModuleNotFoundError: No module named 'pypdf'`，说明当前解释器没装，换一个装了的解释器运行即可。

在工作区根目录执行（即包含 `data/`、`_source/`、`annual_meeting/` 的目录）：

```bash
SKILL=.workbuddy/skills/buffett-annual-meeting

python $SKILL/scripts/buffett.py --year 2024 init      # 新年份：生成配置骨架（已有配置可跳过）
python $SKILL/scripts/buffett.py --year 2024 prepare   # 抓页面 + 解析逐字稿 + 解析信件 PDF
python $SKILL/scripts/buffett.py --year 2024 scaffold  # 填好提问章节后：生成候选与分批计划
python $SKILL/scripts/buffett.py --year 2024 build     # check → 生成全部 Markdown → validate
```

`build` 内含 `check`（只读不写：字段齐备、译文条数等于轮次、`quotes.en` 逐字出现在原文、slug 唯一、信件段落译文无缺口）与 `validate`（配置问数与 `q*.md` 一致、片段含中英两节且无 `译文待补`、全库相对链接可解析，并输出英文词数）；任一环节失败即中止，退出码非零。单步修复用 `fetch / extract / letter-extract / check / validate`。

除了脚本校验，**手工抽查一个片段和一节信件**仍是必要的：数字、人名、引述边界是最容易出错的地方。

新增年份的完整流程、JSON 契约与中文写作规范见 `.workbuddy/skills/buffett-annual-meeting/SKILL.md`；可分发的独立版本为 `dist/buffett-annual-meeting.zip`。

## `_source` 目录结构

原始素材按「年份 → 来源类型」归档，脚本只读这里：`derived/` 下是脚本生成的中间结构，删除后可重新生成。

```
_source/
├── 2025/
│   ├── cnbc/
│   │   ├── morning.html          # 上午场页面快照（含 chapters）
│   │   └── afternoon.html        # 下午场页面快照
│   ├── transcript/
│   │   ├── good-investing.txt    # 会后公开整理实录原文
│   │   └── qa2025.json           # 按提问切分的发言轮次 + 时间戳
│   └── letter/
│       ├── 2024ltr.pdf           # 官网原信 PDF（保留官方文件名）
│       ├── letter2024_paras.txt  # PDF 断行重排后的段落文本
│       └── derived/              # 分节结构、段落 ID 校对文本
└── 2024/
    ├── cnbc/
    │   ├── hub.html              # 年会主页
    │   ├── morning.html          # 上午场（含官方逐字稿）
    │   └── afternoon.html        # 下午场（含官方逐字稿）
    ├── transcript/
    │   ├── chapters.json         # 47 个章节 + 发言人轮次 + 时间戳（build 的唯一英文来源）
    │   └── qa_tasks.json         # 遗留文件：早期筛章节的中间产物，脚本已不再读取
    └── letter/
        ├── 2023ltr.pdf           # 官网原信 PDF
        ├── 2023ltr_raw.txt       # pypdf 原始提取文本
        └── derived/              # 分节结构、段落 ID 校对文本
```

2025 成品由旧脚本生成、已定稿冻结，旧构建脚本已随历史存档清理出库；有官方逐字稿的年份（2018–2024）统一走技能里的 `buffett.py`。

## 做新年份时的注意事项

- **1994–2016 主体可批量**：章节里有逐字稿，一个章节通常就是一个提问，抓取与切分成本低；主要工作量是逐章写中文要点与全文翻译（每年约 40–70 章）。
- **早年（1994–1999）章节偏粗**：一个章节可能覆盖多个提问，需按发言人轮次二次切分，并把切出的伪章节写进配置。
- **2026 与 2025 同类**：没有逐字稿，需要先找外部实录并规整成轮次数据，再走 B 路流程。
- **信件按「会议年份 − 1」取**：2024 年会上对应 2023 年报信，2025 年会上对应 2024 年报信（[berkshirehathaway.com/letters](https://www.berkshirehathaway.com/letters/letters.html)）。绩效表的起止年份、利润表列名都随信变化，写在配置里。
- **不要手工改成品**：`annual_meeting/` 下的文件由 `build` 生成，改内容请改 `data/`（含年份配置 `config.json`）后重建，否则下次构建会被覆盖。年度概览顶部的「快速入口」表由 `readme.py` 自动带上中英信件与两场索引，不需要手写。
- **新年度收尾时补两处索引**：在 `annual_meeting/index.md` 的年度索引表加一行，并在同页的「跨年度主题索引」里给每张表补一列（该文件是手写维护的，不由脚本生成），最后确认 `validate` 里 0 断链。

## 免责声明

内容版权归 CNBC 与伯克希尔·哈撒韦所有，本资料集仅作个人学习研究用的结构化整理。中文要点与译文为整理稿，不是官方文本；引用请以原文和官方视频为准。
