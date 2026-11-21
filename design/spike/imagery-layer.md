# Spike: Imagery layer — 意象层

**Status: awaiting owner review** · 2026-11-20 → 2026-11-21 · PR #8 · 回答 `../overall-design.md` 的 open question 4（phrase tables），并替换原来的 Track B（jieba 名词）· 来源：diary → painting handoff（2026-11-19：风格方向、卷轴分区、motif lexicon、`sealed` fallback）、measurement handoff（2026-11-19：聚类实验）、本 session 的讨论 · 相关：`measurement-layer.md`（测量层，和本层并行）

> 语言约定：叙述用中文；技术名词、模型 id 和代码标识保留英文（segment / beat / motif / zone、`claude-sonnet-5-5`、`POST /generate/stream` …），和代码、`overall-design.md` 一一对应。

## Trigger · 起因

测量层给每个 segment 一组情绪数字，但画面**画什么**——每个区域的主意象、哪一段是转折、哪几段属于同一个区域、哪句原文写进画里——要读懂叙事才能定，规则写不出来。原来的 Track B 用 jieba 抽名词，抽到的是日记里点名的东西（申请、推荐信、妈妈），不是作者用来形容内心状态的画面（石头压在胸口、被束缚手脚）。

Owner 的判断（2026-11-20）：意象是个人偏好，不是测量，这一步交给 LLM，结果「看天发挥」可以接受；可复现只要求测量层。

## 约束 · Constraints（owner 定的）

- **意象是口味，不是测量。** LLM 每次挑的不一样可以接受；测量层继续不用 LLM。
- **不用旗舰模型**：用 Sonnet。
- **输出要能被代码拼起来**：内容可以变，结构必须固定。
- **每一步都要看得见**：做成 streaming endpoint，每一步的输出一出来就推出来（2026-11-20）。

## 选项 · Options

| 选项 | 能拿到什么 | 好处 | 代价 | 结论 |
| --- | --- | --- | --- | --- |
| 原 Track B：jieba 名词、地点词、时间词，TF-IDF | 日记点名的东西 | 确定、免费 | 意象指的是内心状态的画面，名词抓不到；也找不到转折、没法把 segment 分组 | 替换 |
| Owner 维护的 motif lexicon，LLM 只挑 id（diary → painting handoff） | Owner 自己的视觉语言 | 最可控 | 要先有词典 v1 | **下一步**：手做，见「意象词典」；有了之后输出里加 lexicon id |
| 和 owner 标注的样例做 embedding 最近邻 | 确定的挑选 | 可复现 | 要先有标注；聚类实验显示 embedding 分不清「文字在做什么」（inner critic 对 self-comfort） | 暂不考虑 |
| **LLM 在固定 schema 下自由写结构** | 区域、转折、motif、原句，一次调用 | 最省事，读叙事最好 | 不可复现 | **POC 先用它** |

## 已定的事 · Decisions

| 议题 | 决定 |
| --- | --- |
| 谁来读意象 | LLM，替换 jieba 的 Track B（2026-11-20） |
| 模型 | Claude Sonnet 5.5（`claude-sonnet-5-5`），不用旗舰（2026-11-20） |
| 和测量层的关系 | 并行：先按规则切段并编号，两层各跑各的，代码按 segment 编号合并（2026-11-20） |
| 输出 | Structured outputs 固定的 JSON（见「LLM 调用」） |
| 拼 prompt | 代码，不是 LLM：数字查表变成短语，数字本身不进 prompt |
| Motif lexicon | Owner 手做，十篇日记、每篇十个候选（2026-11-20） |
| Streaming | `POST /generate/stream`，每一步完成就推一个 server-sent event（2026-11-20） |

## Pipeline

```
entry ─rules─→ numbered segments ─┬─→ measurement (Inference Endpoint) → per segment: 28-label distribution, V/A
                                  └─→ imagery (LLM, one call)          → beats, turning point, motifs, quote lines
                                              ↓ join by segment number (code)
                                  prompt assembly (code) → image model
```

1. **切段**（规则）并编号：两层共用的 key。
2. **并行**：测量层给每个 segment 打分；LLM 读整篇，带着 segment 编号。
3. **合并**（代码）：每个 beat 取它覆盖的 segment 的分布，按字数加权平均；它的 V/A 选一个氛围短语，阈值以上的 top 3 情绪选点缀短语。
4. **拼 prompt**（代码）：固定的 style block，然后从上到下每个区域的 motif、氛围、点缀，最后是原句。
5. **出图。**

**为什么并行。** 等待时间是两路里慢的那一路，不是两路相加；Endpoint 冷启动不会拖住 LLM；两层可以分开测；LLM 也不会被数字带偏。

**并行放弃了什么。** 之前串行的设计里，LLM 看得到数字，从候选里挑点缀；现在点缀只由代码和表决定——更简单，也是确定的。两层也可能不一致：LLM 读到的是安慰，数字读到的是愤怒。两样都进画面，走不同的位置：motif 来自一边，氛围和点缀来自另一边。

## LLM 调用 · The LLM call

**输入**：按编号排好的整篇 segment。System prompt 说明这是什么——owner 自己的日记，读来规划一幅画——以及要返回什么：只要结构，不给建议，不复述内容。Motif 描述内心状态的画面，作者自己用了比喻就借用；英文；日记再低落也保持温暖：悲伤靠距离、大小、变淡来表达，不靠变暗。

**输出**：用 structured outputs 固定，保证能解析。

| 字段 | 内容 |
| --- | --- |
| `beats` | 3 到 6 个，有顺序；每个覆盖一串连续的 segment |
| `beats[].segments` | 覆盖的 segment 编号 |
| `beats[].zone` | 在卷轴上的位置：`outside`（外界、未来）、`struggle`、`core`、`landing`（当下） |
| `beats[].motif` | 一两句英文：这里画什么 |
| `beats[].objects` | 日记点名的具体事物，英文，用来画小框里的场景 |
| `turning_point` | 放在中心、画成最大人物的那个 beat |
| `quote_lines` | 最多两句原文，逐字，写进画里 |

有了 lexicon 之后，每个 beat 加一个 `motif_id`（从词典里选；没有合适的就是 `null`，在 `motif` 里自由写），以及一个 `new_motifs` 列表：词典里没有的新画面，作为候选等 owner 批准才进词典。

**代码检查**：每个 segment 恰好属于一个 beat，顺序不乱；`turning_point` 指向一个存在的 beat；每句原文必须在日记里逐字出现，否则丢掉。被拒或检查不通过，退回 `sealed`（一封折起的信、一扇关着的门），照样出图。

**设置**：`claude-sonnet-5-5` + structured outputs；effort 没测。拒答走 API 的 server-side fallback（`fallbacks: "default"`），被拒的请求在同一次调用里换一个模型重跑。每条输出连同 model id、prompt 版本和日期一起存。

## 意象词典 · The motif lexicon, by hand

把 owner 的视觉语言写下来：这一步把「看天发挥」变成 owner 自己的选择。

1. **十篇日记，一篇一篇，在对话里做。** 每篇列十个候选画面，每个都对应它承载的情绪：作者自己的比喻优先，否则给内心状态配一个画面——不要日记只是点名的东西。
2. **Owner 挑**：每个保留、改写或删掉。保留的变成一条词典条目，或者并进一条已经说了同一件事的条目。
3. **每条存**：id、owner 脑子里的中文说法、出图用的英文 prompt 片段、适用的 zone 和情绪、来自哪几篇日记。
4. **在同样十篇上试 LLM**：先看它自由写的 motif，有了词典再看它挑的 id，和 owner 的选择对比——第一次看这一步读得像不像 owner。

## 代价 · Trade-offs

- **不可复现。** 同一篇日记每次的 motif 都不一样，模型也不接受 `temperature`。输出存下来当数据；和它合并的测量数字仍然固定。
- **费用。** Sonnet 5.5 每百万 token 输入 $2、输出 $10；一篇日记约 1–3k token 输入、1k 输出外加 thinking，估计 1–3 美分，没实测。
- **延迟。** 一次带 thinking 的调用可能要好几秒；并行能把 Endpoint 藏在它后面，或者反过来。Phase 2 的 10 秒限制更紧了。
- **敏感日记。** 读结构是模型最少拒答的一类任务，但自伤、危机内容仍可能改变回复；fallback 和 `sealed` 兜住拒答，这类日记的产品规则还没定。
- **日记文字会发给 LLM provider。** 隐私暂不考虑。
- **英文 motif** 顺带解决了原来「意象词用什么语言」的问题。
- **自由写的 motif 会偏离 owner 的视觉语言**；词典就是把它拉回来的办法。

## 待拍板 · Open questions

1. **两张短语表**：V/A → 氛围短语（每根轴分几档），情绪 → 点缀短语及阈值。候选在 `measurement-layer.md`「从数字到画面」。Phase 1 先用占位表：每轴 3 档、每类情绪一个点缀、阈值 0.1。
2. **Style block**：diary → painting handoff 里的那段，写成代码里的常量；是否原样照搬。
3. **Prompt 长度**：多少个区域、点缀、原句之后，图像模型开始丢东西。
4. **危机类日记**：一篇写自伤的日记还画不画成温暖的画，要不要附求助资源。

## 批准之后 · After this

待拍板的问题答完，把答案写进「已定的事」，标 `Status: decided`。实现时把决定写进 living docs：`overall-design.md` 的 Track B 和 Step 3（已写）、Phase 1 的 streaming endpoint（已写），以及 `flows/` 里的 flow；实现完成的那个 PR 把这份 spike 移到 `archived/`。

## Sources

- Anthropic 模型列表和价格（Claude API reference，缓存于 2026-11-03）：Claude Sonnet 5.5，`claude-sonnet-5-5`，每百万 token $2 / $10。
- diary → painting handoff（2026-11-19）：风格方向、卷轴分区、motif lexicon、`sealed` fallback。
- measurement handoff（2026-11-19）：聚类实验关于 embedding 漏掉什么的结论。
