---
name: buffett-annual-meeting
description: Build or update the year-based Markdown archive of Berkshire Hathaway annual-meeting Q&A and shareholder letters for 1994-2024, the years whose CNBC pages carry an official transcript. Use when adding a meeting year, rebuilding session indexes or the bilingual letter, or checking Chinese translation coverage. 2025 and later are out of scope.
agent_created: true
---

# 伯克希尔年会资料集（1994–2024）

一条流水线：**抓源 → 写中文 JSON → 一条命令出全部 Markdown**。英文是权威文本，中文是整理稿，须标注非官方。

**范围**：只做 1994–2024。这些年份 CNBC 页面带官方逐字稿。2025/2026 只有章节标题、没有逐字稿，工具会直接拒绝——遇到就停下告诉用户本 skill 不支持。

## 产出

```
annual_meeting/<year>/
├── index.md                        # 年度概览、快速入口、主题索引
├── shareholder-letter-zh.md / -en.md
├── morning/index.md + qNN-slug.md  # 一问一文件
└── afternoon/index.md + qNN-slug.md（非问答环节可为 aNN-*.md）
```

`annual_meeting/index.md` 是手工维护的年份总索引，每年加一行。

## 流程（在库根目录执行，`S` 为脚本路径）

```bash
S=.workbuddy/skills/buffett-annual-meeting/scripts/buffett.py
python $S --year 2024 init       # 新年份：读 CNBC hub，生成 data/2024/config.json 骨架
python $S --year 2024 prepare    # 抓取 + 抽章节逐字稿 + 抽信件 PDF（已存在则跳过，可反复跑）
python $S --year 2024 scaffold   # 填好 questions 后：生成英文提问候选 + 分批计划
# …… 写中文 JSON ……
python $S --year 2024 build      # check → 生成全部 md → validate；任一环节失败即中止
```

- `build` 已内置 `check`（校验中文 JSON）与 `validate`（校验链接与产出），不必单独跑。
- `lint` 查译文可读性（破折号/长句/长段/引语拆碎/译名混用），`normalize` 按译名表批量统一人名；两者都可反复跑。
- 单步修复用 `fetch / extract / letter-extract / check / validate`。
- `init` 只在缺配置的新年份用；`prepare` 可反复跑，源文件已在就跳过。
- CNBC 两场视频页有两种命名（`morning-session`／`afternoon-session` 与 `part-1`／`part-2`），`init` 都认；索引里的会场取 `meeting.venue_zh`，缺省为「奥马哈 CHI Health Center」。

## 1 定章节边界

`prepare` 会打印全部章节：编号、场次、时间轴、轮次、标题。据输出把**确实是股东提问**的章节号按顺序填进 `sessions.morning|afternoon.questions`；上午编号 1..N，下午接续编号。填空规则：

| 情况 | 写法 |
|---|---|
| 一个提问分成两三章 | 后续章节 → `continuations: {"40": 39}`，**不要**放进 `questions` |
| 一个章节里塞了多个提问（早期年份偶见） | `splits: {"12": [[0,4],[4,9]]}` + `questions: ["12.1","12.2"]`；区间是 turn 下标左闭右开，末段可写 `null` |
| 非提问但有内容（一季报简报、正式议程） | `appendix: {"3": {"label": "附件 · 一季度业绩简报", "file": "a01-q1-earnings.md", "data_key": "3"}}`；一章不够时加 `also: [6,7,8]` |
| 其余（开场、休会、致谢、插叙） | 留 `non_qa: {"25": "—（午间休会）"}` 备查即可 |

一场完全没有提问（如 2020 线上年会的 Part 1）就把 `questions` 留空数组，并在该场加 `no_qa_note: "一句话说明问答去哪了"`——场次索引与年度概览会如实写「无问答环节」，不再出现「未整理」这类误导文案。

`continuations` 与 `splits` 的译文数组都要覆盖合并后的全部轮次；元数据与译文文件里的键用同一个编号写法（拆章问题就是 `"12.1"`）。

`prepare` 产出的 `_source/<year>/transcript/chapters.json` 是后面所有步骤的底本：

```json
{"n": 30, "session": "afternoon", "title": "Buffett would make Abel ...", "in": 586, "out": 1165,
 "turns": [{"ts": 586.0, "speaker": "Warren Buffett", "text": "And, Becky, go to it."}]}
```

`n` 全年唯一，`in`/`out` 是该场视频内秒数，`turns` 已按发言人合并。

## 2 写中文

`scaffold` 写 `data/<year>/qa_scaffold.json`：`questions`（n / asker / question_en / turn_count / words）+ `batches`（每批 7 问）。**按批做**：每批只读该批章节，产出该批的 `data/<year>/zh/<batches.file>`，写完一批跑一次 `check`。

中文数据按年归入一个目录（`data/<year>/`，一年一目录、自包含）：

| 文件 | 内容 |
|---|---|
| `data/<year>/morning_zh.json`、`afternoon_zh.json` | 每问一条元数据（下） |
| `data/<year>/zh/*.json` | `{"12": ["第1轮译文", "第2轮译文"]}`，一批一个文件 |
| `data/<year>/appendix_zh.json` | `{"3": {title_zh, tags, intro_zh, points, quotes, translation}}` |
| `data/<year>/letter_zh/partN.json` | `{"06-012": "译文"}`，段落 ID 见 `letter_numbered.txt` |

每题元数据：

```json
{"n": 30, "slug": "abel-capital-allocation", "title_zh": "不超过 20 字，说的是问什么",
 "asker_zh": "Becky Quick 代股东提问（姓名，地点）", "question_zh": "2–4 句，去掉寒暄与 (PH)/(unintelligible)",
 "points": ["4–6 条结论，尽量带数字、年份、公司名"],
 "quotes": [{"en": "原文逐字子串", "zh": "准确中译"}], "tags": ["接班", "资本配置"]}
```

`build` 会硬的约束：`quotes.en` 必须是原文逐字子串；`slug` 小写连字符且同年唯一；`points` 不写提问者背景。译文数组应与该问轮次数一一对应（不合并不拆分不省略）；**翻译遇到异常——译文缺失、含空轮次或轮次数不匹配——不再中断构建，该页跳过「中文全文」仅保留英文原文**（build 打 warn；信件缺段同理，该段落保留英文原文）。

译文照满轮次翻译，含语气词与笑声；概括只放在 `points`。

### 中文表达规范

译文是给人读的中文，不是对照稿。逐句镜像英文句法是最常见的质量塌陷，写的时候按下面十条改：

1. **句内重组**。英文的主从句顺序、后置定语、插入语一律按中文语序重排，允许在**同一轮内**拆句、并句、换主语。
   `the decision process is really quite interesting in a certain way` → 「这个决策过程其实挺有意思」，不写「在某种意义上相当有意思」。
2. **插入语不用破折号代偿**。英语夹注靠破折号，中文优先改成前置状语、括号（），或拆成独立短句。每轮破折号不超过 2 对。
3. **单句 ≤ 60 字**，超过就断。中文靠短句推进。
4. **单轮超 300 字要分段**，在语义转折处插空行 `\\n\\n`，`qa.py` 会原样输出成多段。整轮两三千字不分段是最伤可读性的。
5. **引语合并**。同一提问的多句引语合成一个「」，中间不闭合；跨轮不合并。
6. **口误只整理一次**。语气词、笑声（（笑））、自我更正都保留，但同一个意思重复两遍的只留一遍；`(PH)` → （音），`(unintelligible)` → （听不清）。
7. **虚词不逐字对应**。`Well` / `Now` / `So` / `I mean` 多数不译或作「嗯」「这个」「我是说」，每轮至多一次。
8. **数字口语化**。`about` / `roughly` → 约；`billion` → 亿；百分比用阿拉伯数字；不擅自四舍五入。
9. **保留英文的专名**首次出现可加中文括注，如「GEICO（盖可保险）」，后文不再加。
10. **不许省略**：轮次数必须对齐，但允许合并同义重复、删纯填充词。

`lint` 会把违反 2/3/4/5 与中英长度比异常的轮次点出来，写完一批跑一次。

## 3 信件

`letter` 段声明：来源年份、`pdf`、`published`、`intro_en/zh`、`sections`（`id` / `title_en` / `title_zh`，首个 id 即卷首）、可选 `earnings_table`（PDF 常丢合计行，行值自己写全）、`performance_table`（`years` / `compounded` / `overall` / 注释）。没有季度表的年份（如 2021 信）直接省略 `earnings_table`。

PDF 抽坏的兜底：`text_fixups`（全局替换对）、`para_fixups`（段落 ID → 新文本，`null` 删段）。改完 fixup 必须重跑 `letter-extract` 再翻译，因为后续 ID 会移位。老坑见 `references/quirks.md`。

## 术语与数字

人名固定译法（**同一人在同一篇里不混用英文**，lint 会查）：

| 英文 | 中文 |
|---|---|
| Warren Buffett | 沃伦·巴菲特 |
| Greg Abel | 格雷格·阿贝尔 |
| Ajit Jain | 阿吉特·贾因 |
| Charlie Munger | 查理·芒格 |
| Becky Quick | 贝基·奎克 |
| Ted Weschler | 泰德·韦施勒 |
| Todd Combs | 托德·康姆斯 |
| 伯克希尔·哈撒韦 | Berkshire Hathaway |

`GEICO`、`BNSF`、`Pilot`、`BHE`、`GAAP`、`S&P 500` 保留英文。`$182 billion` → 1820 亿美元；区间用 `—`（1965—2024）；引语用 `「」`；不擅自四舍五入（about → 约）。

改译名用 `normalize`（按内置表批量替换，幂等），不要手改 md。

## 收尾

- `annual_meeting/index.md` 是手工索引：加一行（年份、概览/两封信/两场索引、规模、逐字稿来源）。
- 不改生成的 md，改 JSON 再 `build`。

## 排错

| 现象 | 处理 |
|---|---|
| Access Denied / 403 | `fetch` 已带浏览器 UA；再失败看网络或代理 |
| `window.__c_data not found` | CNBC 换壳，检查 HTML 后改 `cnbc.cache` |
| 章节轮次为 0 | 该年无官方逐字稿（2025+），本工具不支持 |
| 弯引号乱码 `â€™` | `repair` 已处理；新形态就补编码尝试 |
| 段落数差一 | 表格行漏进正文，加跳过规则或把表移进年份配置 |
| 译文对不上 | 比 `len(translation)` 与 `len(turns)`，不许补位凑数 |

参考：`references/quirks.md`（PDF 抽取老坑与历年差异）、`assets/year-config.example.json`（配置样例）。
