# 抽取老坑与历年差异

只在出问题时读。`prepare` 正常跑完就不必看。

## 信件 PDF（`letter-extract`）

| 现象 | 原因与处理 |
|---|---|
| 成绩单跑到正文之前 | 早期信件把 59 年成绩单印在第 1 页且无标题。把成绩单设为 `sections[0]`，并令 `performance_table.section_id` 等于该 id，表格就落回原位 |
| 段落数比预期多一 | 表格行漏进正文。看 `letter_numbered.txt` 定位，把该表补进 `earnings_table`，或给正文加跳过规则 |
| 标题与下一段粘在一起 | PDF 断块所致；`parse` 按已知标题前缀切开，仍失败就用 `text_fixups` |
| 数字被空格拆开（`8 . 1`） | `parse` 会重连数字与小数点；分数 `61⁄ 2` 也重连为 `6 1/2` |
| 项目符号变成 `U+0081` | 开 `split_bullets: true`，每条成为独立段落（各自独占一条译文） |
| 17 KB 的巨块（十五大持仓表） | 点线表格。`parse` 只保留点线之上的引导句，表格本身丢弃 |
| 2016 信的 8 张表全丢、只剩引导句 | 该信的点线表横跨多个块且列被拉扯开（`$ 822 … $ 45,081`），`parse` 与 `_prose` 都救不回。做法：用 `para_fixups` 把引导段换成「引导句 + Markdown 表」，数字从 PDF 的**纯文本模式**（`Page.extract_text()`，不加 `layout`）逐行核对后手写；表头与合计行由自己补全（PDF 的合计行常单独成块，如 `$2,131 $1,837 $ 91,577 $ 87,722`）|
| 季度利润表整段挤成一行 | 以 `Earnings in $ billions` 开头，直接跳过，改用 `earnings_table.rows` 重建（PDF 常丢合计行，合计值自己写全） |
| 某段彻底废掉 | `para_fixups` 换文本，`null` 删段；改完重跑 `letter-extract` 再翻译，后续 ID 会移位 |

## 年会页面（`extract`）

- 1994–2024 都是细粒度章节（1995 年 83 章、2019 年 67 章），逐字稿完整；偶尔一章含两个提问，用 `splits` 拆。
- 早期页面发言人标签不一致（`MR. BUFFETT`、`AUDIENCE`），当前 `SPEAKER` 正则能吃掉；出现新标签就补 `cnbc.py`。
- 时间戳是**该场视频内的相对时间**，不是当天钟表时间。
- `window.__c_data` 结构变了才需要动 `cnbc.cache`；抓到 `Access Denied` 是 UA 问题。
- 2017 年的页面已换成 Next.js 外壳，逐字稿在 `self.__next_f.push([1,"..."])` 的 React Flight 流里，不再有 `window.__c_data`；`cnbc.cache` 已兼容两种形态（先找 `window.__c_data`，找不到再拼 Flight 字符串、定位 `"transcript":`）。

## 已建年份的多章提问（重建时对照）

| 年份 | 合并情况 |
|---|---|
| 2024 | 第 40 章并入下午第 9 问 |
| 2023 | 8+9 → 上午第 3 问；34 → 下午第 1 问；52 → 下午第 18 问 |
| 2022 | 10→9、13→12、15/16→14、21→20、25→24、38→37、41→40、43→42；开场 Q1 复盘跨第 5–8 章，用 `appendix.also` |
| 2017 | 36 → 上午第 29 问（会计新规接精密铸件）；66 → 下午第 24 问（EBITDA 答完）；第 2 章一季度简报 → `appendix`；1、3、4、5、28、56、68–74 章 → `non_qa` |

## 重建纪律

- 生成的 md 不改；改 `data/<year>/config.json` 或中文 JSON，再 `build`。
- `_source/<year>` 保持不可变；CNBC 改版就重存快照，并在年度 README 记抓取日期。
- `python -m compileall scripts` 可在改脚本后快速查语法。
