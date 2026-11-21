# Spike: Measurement layer — 情绪测量层

**Status: decided** · 2026-11-19 → 2026-11-21 · PR #8 · 回答 `../overall-design.md` 原来的 open question「Emotion vocabulary」和「Access to emotion inference」· 来源：两份 2026-11-19 的 session handoff（measurement、diary → painting）、本 session 的讨论和 probe · 相关：`imagery-layer.md`（意象层，和本层并行）

> 语言约定：叙述用中文；技术名词、模型 id 和代码标识保留英文（segment、valence / arousal、`Horizon-Labs/multilingual-emotions-base`、Inference Endpoint …），和代码、`overall-design.md` 一一对应。

## Trigger · 起因

日记要变成画，先要把每个 segment 的情绪量化成数字：画面的氛围（光线、冷暖、留白）和点缀都从这些数字来。Owner 给了几条硬约束，最重要的一条是**测量层不用 LLM**：同一段文字永远得到同一组数。这份 spike 记录测量层怎么选出来的：候选、选了哪个、代价，以及几次 probe 的结果。

## 约束 · Constraints（owner 定的）

- **按情绪转折分段。** Owner 写日记时在情绪转折处换行，所以 segment 优先按换行切。现有 36 条 dump 里有 34 条没有换行，兜底做法是按句子拼成 200–300 字一段。
- **固定模型，不用 LLM。** 同一段文字永远得到同一组数；每条输出记下 model id 和 revision。
- **Hosted inference**（Hugging Face 或类似服务），不跑本地。隐私暂不考虑。
- **许可清楚**：Hub 上现成的开源模型，不用去问作者的权重。
- **准确度先不管**，先让数据流起来。
- **已知弱点**：依赖上文的情绪（指代前文、反转、只有在挣扎之后才说得通的自我安慰）。

## 设计方法 · How the design was reached

分两遍：先**从头往后推**，看能测什么；再**从出图往回推**，看测量层必须交出什么。

### 从头往后推 · Forward, from the text

1. **LLM 给每篇打分**：最早的想法，放弃了。分数每次都会飘，而且现在的 Claude 模型不接受 `temperature`，没法把飘动调小；开源 LLM 在批量 GPU 推理下，temperature 0 也不保证逐位一致。
2. **固定模型**：Hub 上没有中文的 V/A 模型，中文情绪分类器的成绩一般（厂商自报，中文社交媒体上 macro-F1 0.44–0.56）。
3. **自己训一个 head**（冻结 embedding + BRIGHTER 中文数据，CC-BY-4.0）：owner 否掉了，不训练。
4. **先翻译再用英文资源**：英文有直接输出 V/A 的模型，但 Hub 上那个（`BenRongey/deberta-v3-base-emobank-vad`）是个人上传，模型卡是自动生成的。
5. **Mendes & Martins（ECIR 2023）**：同行评审过的多语言 V/A 模型，训练数据里有中文，最好引用；放弃了，权重没有许可，训练数据里还有仅限研究用途的数据集。
6. **许可干净、Hub 上现成**：剩下三条路（见「选项」）。先选了方法 1，因为两个模型都有 provider 直接调用；probe 之后发现翻译会丢内容、编内容，改成直接读中文。

### 从出图往回推 · Backward, from the painting

从出图的 prompt 出发（diary → painting handoff 里的风格讨论），看每一部分要什么：

| Prompt 的部分 | 决定什么 | 需要测量层给什么 |
| --- | --- | --- |
| Style block | 谁在画 | 不需要，固定 |
| 竖卷轴从上到下的各个区域 | 一篇的走势 | **有顺序的** segment |
| 中心人物 | 转折点 | 一串 valence，用来找转折 |
| 每个区域的氛围（光线、冷暖、密度） | 温度和天气 | 每个 segment 的 **V 和 A** |
| 每个区域的点缀（落叶、一点朱红、亮起来的窗） | 质感 | 每个 segment **带名字和分数的 top 情绪** |
| 每个区域的主意象 | 画什么 | 原文，读叙事（见 `imagery-layer.md`） |

所以测量层要按顺序、给每个 segment 交出**一个带名字的情绪分布，外加一个 V/A 点**。只输出 V/A 的模型（Mendes & Martins、EmoBank DeBERTa）能管氛围，管不了点缀；分布两样都能管，因为 V/A 可以从分布算出来。这是 28 标签分类器在许可之外胜出的原因：它的输出覆盖了上表每一行。

## 选项 · Options

| 候选 | 输出 | 中文 | 现在能直接调吗 | 许可 | 好处 | 代价 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LLM 结构化打分 | 想要什么都行 | 能 | 能 | — | 最懂上下文 | 不可复现 | 放弃 |
| `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` zero-shot（原来的 Phase 1 默认） | 每个自写 label 的 entailment 分数 | 能 | hf-inference | MIT | 标签随便写 | 分数取决于 label 的措辞；词表是自己编的，没有现成的环形坐标 | 替换 |
| `MilaNLProc/xlm-emo-t` | 4 类 | 能 | hf-inference | 取决于源数据 | 现成 | 太粗，做不了点缀 | 不选 |
| `tabularisai/multilingual-emotion-classification` | 11 类 | 能 | hf-inference | Hub 上 MIT，别处标 NC | 现成 | 许可矛盾 | 不选 |
| `BenRongey/deberta-v3-base-emobank-vad` | V、A、D | 翻译后 | 要开 endpoint | MIT（EmoBank CC-BY-SA 4.0） | 直接出 V/A | 模型卡不全；没有分布 | 不选 |
| Mendes & Martins，XLM-R-large | V、A | 能 | 要自己托管 | 代码 MIT，权重无 | 可引用 | 许可 | 放弃 |
| **`Horizon-Labs/multilingual-emotions-base` / `-small`** | 28 个 GoEmotions 标签 | **直接读** | 要开 endpoint 或 Space | Apache-2.0 | 不用翻译；标签和方法 1 一样 | 要自己托管 | **POC 选它** |
| 方法 1：`Helsinki-NLP/opus-mt-zh-en` → `SamLowe/roberta-base-go_emotions` | 28 个 GoEmotions 标签 | 翻译后 | 两个都在 hf-inference | CC-BY-4.0 → MIT（GoEmotions Apache-2.0） | 不用托管 | 翻译会丢、会编（见「代价」） | 第一选择，现在是 fallback |

## 已定的事 · Decisions

| 议题 | 决定 |
| --- | --- |
| 测量模型 | `Horizon-Labs/multilingual-emotions-base`（或 `-small`），直接读中文，不翻译（2026-11-20） |
| 输出 | 每个 segment 28 个独立的 sigmoid 分数（27 种情绪 + `neutral`，multi-label），归一化成分布；原始分数也保留 |
| V/A | 算出来的，不是测出来的：分布加权平均一张固定的坐标表；表带版本号，v0 见下 |
| 托管 | 专用的 Hugging Face Inference Endpoint（2026-11-20）。实例大小、`base` 还是 `small`，部署时定 |
| 不用 LLM | 测量层只有规则和固定模型（2026-11-19） |
| Fallback | 直接读中文效果不好时，退回方法 1：先翻译，再用英文分类器，标签一样，下游不用动 |

### 怎么跑 · Pipeline

1. **切段**（规则）：按换行切；没有换行的长段按句子拼成 ~200–300 字；太短的尾巴并进相邻段。
2. **打分**：Horizon 模型读每个中文 segment，给出 28 个 sigmoid 分数。模型基于 mmBERT，用 GoEmotions 加它的 35 种语言机器翻译训练，训练长度最多 256 token；200–300 字的 segment 大约 120–150 token。
3. **归一化**：28 个分数归一化到和为 1，图表和点缀用这个分布；原始分数也存。
4. **V/A**：分布加权平均坐标表，每个标签一个 [−1, 1] 的 (V, A) 点，`neutral` 在原点。

每个 segment 存：原文、原始分数、分布、V、A、model id 和 revision、坐标表版本。

`base` 在模型卡的 benchmark 上分数更高（BRIGHTER 六类情绪，28 种语言的人工标注文本，macro-F1 0.420 对 0.406）；`small` 不到它一半大。Apache-2.0 要求保留许可声明，在项目文档里列出即可。

### 托管 · Hosting

两个 Horizon 模型都没有 inference provider（Hub API，2026-11-20），所以「调 Hugging Face API」之前，要先自己把模型跑起来。两种方式都不用给模型写自定义代码：它是标准的 `text-classification` 模型，config 里标了 multi-label，标准 pipeline 会自动用 sigmoid；请求时要求返回全部 28 个标签，就是完整分布。

| | Inference Endpoint ✓ | Space（Docker 或 Gradio） |
| --- | --- | --- |
| 是什么 | Hugging Face 托管的专用 API，部署时选模型 | 自己写一个约 20 行的小服务，加载模型、接 HTTP |
| 硬件和价格 | CPU 每小时 $0.033 起（AWS，1 vCPU、2 GB）；2 vCPU、4 GB 是 $0.067；运行期间按分钟计费；可以暂停或缩到零 | CPU Basic：2 vCPU、16 GB，硬件免费 |
| 账户 | 有效订阅 + 绑卡 | 建 Docker 或 Gradio Space 要 PRO |
| 闲置 | 缩到零之后，下一个请求重新加载模型 | 48 小时没人用会睡眠，下一个请求唤醒 |
| Revision | 部署时指定 commit，模型版本固定 | 由代码加载的版本决定 |

**选 Inference Endpoint**：最接近「直接调一个 API」，不用写服务，部署时 revision 就固定了。

### 坐标表 v0 · Provisional table（V, A）

由我们参照 Russell（1980）的环形位置写，没有许可问题；owner 可以调。

| | | | |
| --- | --- | --- | --- |
| admiration 0.6, 0.3 | amusement 0.7, 0.5 | anger −0.7, 0.7 | annoyance −0.5, 0.4 |
| approval 0.5, 0.1 | caring 0.6, 0.0 | confusion −0.3, 0.3 | curiosity 0.3, 0.4 |
| desire 0.4, 0.5 | disappointment −0.6, −0.3 | disapproval −0.5, 0.2 | disgust −0.7, 0.4 |
| embarrassment −0.5, 0.4 | excitement 0.7, 0.8 | fear −0.7, 0.7 | gratitude 0.7, 0.1 |
| grief −0.8, −0.4 | joy 0.8, 0.5 | love 0.8, 0.3 | nervousness −0.5, 0.6 |
| optimism 0.6, 0.3 | pride 0.6, 0.4 | realization 0.1, 0.3 | relief 0.5, −0.4 |
| remorse −0.6, −0.2 | sadness −0.7, −0.4 | surprise 0.2, 0.7 | neutral 0, 0 |

### Fallback：方法 1（先翻译）

直接读中文效果不好时，翻成英文再用英文分类器，28 个标签一样，坐标表和下游都不用动。Probe 已经定下的做法：

1. **切段**同上。
2. **翻译单元约 40 字**，用 `Helsinki-NLP/opus-mt-zh-en`（beam search，6 beams，来自模型自带的 generation config），翻完拼回去。40 不是模型的上限（它能读 512 token，这里最长的 segment 才 144），是从一篇日记试出来的暂定值：打开输出上限之后，没有任何单元丢内容的最大尺寸。单元由规则切，owner 写日记很少用句号，所以逗号当小句边界：
   - 先在硬边界切：换行和 `。！？!?…；`；
   - 还超过上限的，在软边界（`，、：—`）切成小句，再拼回去，不超过上限；英文单词不切；
   - 生成加上限：不许重复 3 词组，输出长度按输入长度封顶；
   - 10 字以上的单元，按「英文词数 ÷ 源单位数」检查（一个汉字算一个，一个英文词也算一个）：低于约 0.3 说明丢了内容，切细重翻；高于约 1.2 说明循环穿过了上限，在输出里标出来。这个检查抓得到「一块丢了大半」，抓不到「长块只丢了最后一句」。
3. **分类**：英文 segment 交给 `SamLowe/roberta-base-go_emotions`，28 个 sigmoid 分数。
4. **归一化**、**V/A** 同上。

这个变体额外要存：译文，以及两个模型各自的 id 和 revision。CC-BY-4.0（翻译模型）要求署名，MIT 保留声明。

商用翻译 API（DeepL、Google、Azure）翻得应该比 `opus-mt` 好很多，但都不能固定模型版本（DeepL 明说可能随时换掉某个 model type 背后的模型），所以用它的话，译文只能翻一次存下来，当原始数据，不能重算。

## 代价 · Trade-offs

### V/A 是算出来的，不是测出来的

- **只和坐标表一样好。** 模型给的是情绪的名字，名字在环上的位置是我们定的。换了表，所有 V/A 都变，所以表要带版本。
- **混合 segment 会往中心靠。** 一半 sadness 一半 joy，落在 (0, 0) 附近，和 neutral 是同一个点。点丢了混合，分布还留着；以后可以用分布的离散程度或矛盾度（evaluative space model；Griffin 指数 (P+N)/2 − |P−N|）找回来。
- **坐标从哪来：**
  - 我们参照 Russell（1980）自己写：没有许可问题，是默认做法，v0 见上；
  - NRC-VAD：之前讨论里提过，但它的条款是非商业、不许再分发，而它的数值会被打包进我们的表；
  - Warriner et al.（2013）norms：许可没查。
- **归一化也是一个选择。** 28 个 sigmoid 分数互相独立，加起来不等于 1（probe 里在 0.35–2.41 之间）。归一化之后各段能比较，但看不出模型整体「多确定」；`neutral` 在原点，会按它的分数把每个点往中心拉。

### 翻译：POC 为什么跳过它

这些都是方法 1 的发现，也是 POC 改成直接读中文的原因；方法 1 回来时它们仍然成立。

- **Translate-test 是跨语言情感分析的标准做法。** `opus-mt-zh-en` 是个小模型：约 7800 万参数，2020 年用逐句对齐的平行语料训练，只在 Tatoeba 短句上评测（BLEU 36.1）。
- **本地词活不下来。** 训练语料里没有「套瓷」（申请前给导师发邮件），译成了 "put on the china"，有一次还成了一个不相干的露骨词。人名、错别字也一样：一个朋友的名字成了 "a bear"；「幸苦」（应为「辛苦」）把 "you've worked so hard" 变成了 "you're so lucky"。分类器主要看周围的情绪词，名词翻错代价不大；但错别字正好在表达情绪的那句里，读出来的情绪就变了。
  - **一个可选的补救，没采用**：owner 维护一张词表，翻译前按规则把这类词换成普通中文。Probe 里「去联系教授」→ "contact the professor"，「去给教授发邮件」→ "e-mail the professor"，名字换成「朋友」→ "friends"。换成英文反而更糟：中文句子里夹一段英文，整句都翻乱了。代价是多一张表要维护，而且只能覆盖已经注意到的词。
- **长输入和短输入坏法不同。** 长输入会悄悄丢掉后面的句子；短输入或重复的输入会循环、编内容（"omg" 成了 "I don't know what you're talking about"）。夹在中文里的英文词原样保留。
- **翻译粒度会改变测量结果。** 八种单元大小下，segment 2 的 V 从 −0.30 变到 +0.34；另外两段变化小得多（−0.17 到 −0.36；+0.28 到 +0.41）。一段里挤了四个转折，怎么切都不稳；真正的解法是按换行分段，不是调单元大小。单元也意味着更多请求：每个单元一次，除非 provider 接受批量。
- **为什么输出要封顶。** 翻译循环时，输出长度和输入没关系，最多能一直生成到 512 token（probe 里 40 个字翻出了 46 个 "no"）。代价有三：循环内容被分类器当成作者写的话；循环够长，会把 segment 里真正的句子挤出分类器自己 512 token 的读取范围；hf-inference 按计算时长计费，循环就是在花钱。不许重复 3 词组这条规则阻止循环本身；长度上限（每个源字符 1.5 个输出 token，再加 8）兜底规则没拦住的循环，定得比正常译文宽，probe 里没有任何单元碰到。代价：这条规则也会压掉作者故意写的重复（「痛苦痛苦痛苦」成了 "pain and suffering"）；hf-inference 能不能接收这两个参数没有验证。

### 标签体系来自英文 Reddit

- GoEmotions 是 5.8 万条英文 Reddit 评论，由读者标注：它测的是**读者读出来的情绪**，不是作者当时的感受。
- 日记既不是 Reddit 也不是英文。Horizon 的中文来自这些评论的机器翻译，不是中文原生文本。Top 标签有噪声；只取阈值以上的 top 3（见「从数字到画面」）能滤掉一部分，模型自带按 GoEmotions 调好的每标签阈值。

### 上下文

分类器一次只看一个 segment，只有在挣扎之后才说得通的自我安慰，只按它自己的字打分。按换行分段能让每段的情绪基本一致，解决大部分段内问题；跨段的走势由意象层读叙事时处理，不在测量层。

### 可复现

- 本地两次运行，输出逐字节一致；两个 Horizon 模型各自跑两次也一致。
- 托管后，Inference Endpoint 从指定的 commit 部署，模型作者更新了也不会影响，直到我们重新部署。每条输出记下 revision，变化看得见。托管的硬件能不能逐位复现本地分数，没验证。

### 访问和费用

- **直接读中文（已选）**：模型由我们托管，Endpoint 运行期间按分钟计费，或者 Space 用免费硬件但建 Space 要 PRO（见「托管」）。
- **方法 1**：两个模型都在 hf-inference 上，不用托管，但调用要 credits：hf-inference 按计算时长收费；免费账户没有每月额度，PRO 每月 $2。

## 实跑 · Probe runs（2026-11-19 → 20）

用 diary → painting handoff 里的一篇日记（约 1,260 字，没有换行），在容器里用 CPU 跑，模型 revision 和 Hub 上的一致。兜底切法切成三段。日记原文不在这里复述。

### 方法 1（`opus-mt-zh-en` `cf10909`，`roberta-base-go_emotions` `d750483`）

| Segment | 内容（转述） | 字数 | 翻译方式 | Top 3（归一化） | V | A |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 连着几天低落；外界对钱和规划的压力 | 180 | 整段 | curiosity .32, sadness .26, disappointment .14 | −0.20 | 0.06 |
| | | | 按 `。！？` | curiosity .29, sadness .26, disappointment .17 | −0.23 | 0.04 |
| 2 | 被事情淹没、安慰自己、内心的检察官、发火 | 219 | 整段 | admiration .37, annoyance .19, anger .10 | +0.15 | 0.32 |
| | | | 按 `。！？` | sadness .38, disappointment .15, curiosity .09 | −0.28 | −0.08 |
| 3 | 回到当下，和妈妈聊聊 | 56 | 整段 | approval .70, neutral .15, admiration .04 | +0.41 | 0.11 |

- **走势出来了**：负 → 负 → 正，落在日记的落点上。
- **Segment 2 是问题段。** 它挤了四个转折（被淹没、安慰自己、检察官、发火），因为这篇没有换行。整段翻译时结尾的愤怒被丢了，"you're the best" 占了上风（`admiration`）；按 `。！？` 切开翻，`sadness` 占上风。按 owner 换行的习惯，这段大概会是三四段。
- **反问被读成 `curiosity`。** 「为什么会这样呢」这类反问被打成 curiosity，而 v0 把它放在正效价：标签体系读错日记的一个例子。
- **Segment 3 是很短的尾巴**（56 字），打包规则应该把它并进相邻段。

### 直接读中文（`-small` `ac26dad`，`-base` `4f95ad2`）

| Segment | 内容（转述） | Tokens | `-small` top 3 | V / A | `-base` top 3 | V / A |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 低落；外界压力 | 117 | sadness .45, love .16, curiosity .15 | −0.15 / −0.02 | curiosity .29, sadness .26, confusion .21 | −0.17 / 0.11 |
| 2 | 被淹没、安慰自己、检察官、发火 | 143 | anger .41, annoyance .21, optimism .12 | −0.29 / 0.43 | annoyance .21, neutral .15, anger .14 | −0.10 / 0.24 |
| 3 | 回到当下，和妈妈聊聊 | 35 | neutral .53, caring .20, approval .17 | +0.21 / 0.05 | neutral .31, caring .29, approval .25 | +0.33 / 0.06 |

- **走势还在**：负 → 负 → 正。
- **Segment 2 的愤怒被看见了。** 所有翻译过的版本要么丢了它，要么排得很低；读中文时两个模型都把 anger 或 annoyance 排第一，arousal 也是三段里最高的，更接近这段写的东西。
- **两个大小在细节上不一致。** Segment 1 上 `small` 以 sadness 领先，`base` 以 curiosity 领先；segment 2 上 `base` 把分数摊开，`neutral` 排第二。只有一篇、没有标注，看不出谁更好。
- **模型「多确定」差别很大。** Segment 2 上 `small` 的 28 个原始分数加起来只有 0.35，segment 1 上 `base` 是 2.41；归一化把这个差别藏起来了。

### 翻译单元大小（方法 1）

还是 segment 2，只改翻译单元，不加输出上限（打包在软边界切；分类器仍然读整段译文）：

| 单元 | 块数 | V | 翻译出了什么问题 |
| --- | --- | --- | --- |
| 整段 | 1 | +0.15 | 结尾的愤怒没了 |
| 按 `。！？` | 3 | −0.28 | 148 字那一句里的自我安慰没了 |
| 拼到 ≤ 80 字 | 3 | −0.06 | 一个 80 字的块只翻出一句短话 |
| 拼到 ≤ 40 字 | 7 | +0.20 | 一块翻成了 46 个 "no, no, no…" |
| 拼到 ≤ 20 字 | 13 | −0.11 | — |
| 每个小句一块 | 24 | −0.30 | 「痛苦痛苦痛苦」无限循环成 "the pain"；"omg" 成了 "I don't know what you're talking about"；乱补主语 |

- **两种失败在两头**：长输入丢内容，短输入或重复输入会循环、编内容。英文词数和汉字数的比例能把它们分开：完整译文约 0.4–0.8，丢内容的那块 0.19，循环 1.15–9.7。
- **输出上限消掉了循环。** 不许重复 3 词组、加上长度上限之后，46 个 "no" 变成 "No, the prosecutor's always in judge. Fuck, leave me alone! It's more painful, painful and painful"，无限的 "the pain" 变成 "pain and suffering"。

整篇加上输出上限：

| 单元 | 块数 | 被标为丢内容 | V，segment 1 / 2 / 3 |
| --- | --- | --- | --- |
| 整段 | 3 | 0 | −0.25 / +0.03 / +0.40 |
| 按 `。！？` | 10 | 0 | −0.23 / +0.34 / +0.40 |
| 拼到 ≤ 80 字 | 7 | 1 | −0.36 / −0.06 / +0.40 |
| 拼到 ≤ 60 字 | 9 | 1 | −0.17 / +0.27 / +0.40 |
| 拼到 ≤ 40 字 | 14 | 0 | −0.31 / −0.06 / +0.40 |
| 拼到 ≤ 30 字 | 19 | 0 | −0.30 / +0.09 / +0.35 |
| 拼到 ≤ 20 字 | 29 | 1，误报 | −0.29 / −0.11 / +0.35 |
| 每个小句一块 | 48 | 1，误报 | −0.33 / −0.29 / +0.36 |

- **任何大小都没有循环，也没有单元碰到长度上限。**
- **比例检查漏掉部分丢失。** 整段和 `。！？` 两行什么都没标出，但不加上限时，同样这些单元丢了最后几句（见上表）。
- **两次误报**是一个几乎只有一个英文词的小句，按字母数算了；所以英文词按一个单位算。
- **为什么是 40**：≤ 40 和 ≤ 30 都干净；40 请求更少、每块上下文更多，乱补主语更少。只有一篇证据很薄，定数字之前应该在更多日记上重跑。

## 从数字到画面 · From the numbers to the painting

从出图往回推的细节；来源：附录里的讨论。意象层怎么接这些数字，见 `imagery-layer.md`。

### 三个角色

Style block 决定**谁在画**，motif 决定**画什么**，情绪分布决定**这幅画的温度和天气**。风格固定，不等于情绪固定：Nilima Sheikh 的两幅卷轴共用一套视觉语言，情绪温度却完全不同。

### 28 个数字不直接进 prompt

图像模型读不懂 "sadness 0.18"，修饰词一多还会互相抵消。中间要有一层翻译：分布 → 少量视觉参数 → 事先写好的固定短语。这一层全是代码和表，不是 LLM，同样的分布永远得到同样的短语，表由 owner 来调。

- **氛围：来自 V 和 A。**
  - 光线：清晨、正午、黄昏
  - 暖色范围内的冷暖和饱和度
  - 密度和留白
- **点缀：阈值以上的 top 3 情绪**，各对应一个小点缀：

  | 情绪 | 点缀 |
  | --- | --- |
  | sadness, grief | 飘落的叶子；局部颜色变淡 |
  | nervousness, fear | 小框挤得更紧；人物更小 |
  | anger, annoyance | 一点朱红；纹样边缘更尖 |
  | caring, love, gratitude | 暖灯、金色纹样、开着的花 |
  | optimism, relief | 伸出画外的小路；地平线上的晨光 |
  | confusion | 分岔、绕弯的小路 |
  | realization | 一扇亮起来的窗 |

- **按 segment，不按整篇。** 整篇一个分布会把起伏抹平；每段一个分布，卷轴每个区域可以单独调：顶部雾蒙蒙的、淡，底部暖、亮。画面的细腻主要从这里来。
- **护栏写死在代码里。** 每个参数都有上下限。Sadness 只能让区域更淡、更空、更远，不能更暗；温暖的底线固定。

### 图表

饼图看得清一段的构成，看不出顺序。看走势用堆叠面积图：横轴是 segment 顺序，每种情绪一条色带，形状本身就像一条卷轴。两种都做：整篇看面积图，点开看单段的饼图。

## 批准之后 · After this

实现时把这里的决定写进 living docs：`overall-design.md` 的 Track A（已写）、Step 1 的切段上限，以及 `flows/` 里测量这一步的 flow。实现完成的那个 PR 把这份 spike `git mv` 到 `archived/`。

## Sources

- [SamLowe/roberta-base-go_emotions](https://huggingface.co/SamLowe/roberta-base-go_emotions)
- [Helsinki-NLP/opus-mt-zh-en](https://huggingface.co/Helsinki-NLP/opus-mt-zh-en)
- [GoEmotions (Demszky et al., ACL 2020)](https://arxiv.org/abs/2005.00547)
- [GoEmotions dataset](https://huggingface.co/datasets/google-research-datasets/go_emotions)
- [Horizon-Labs/multilingual-emotions-base](https://huggingface.co/Horizon-Labs/multilingual-emotions-base)
- [Horizon-Labs/multilingual-emotions-small](https://huggingface.co/Horizon-Labs/multilingual-emotions-small)
- [Inference Endpoints pricing](https://huggingface.co/docs/inference-endpoints/pricing)
- [Spaces hardware and sleep rules](https://huggingface.co/docs/hub/spaces-gpus)
- [DeepL: understanding model types](https://developers.deepl.com/docs/translate/understanding-model-types)
- [Mendes & Martins, ECIR 2023](https://arxiv.org/abs/2302.14021)
- [multilingual_va_prediction (README, LICENSE)](https://github.com/gmendes9/multilingual_va_prediction)
- [BenRongey/deberta-v3-base-emobank-vad](https://huggingface.co/BenRongey/deberta-v3-base-emobank-vad)
- [NRC VAD Lexicon — terms of use](https://www.saifmohammad.com/WebPages/nrc-vad.html)
- Russell, J. A. (1980). A circumplex model of affect. *Journal of Personality and Social Psychology*, 39(6), 1161–1178.
- [Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing)
- Hub API（`/api/models/<id>?expand[]=inferenceProviderMapping`）：方法 1 的两个模型在 hf-inference 上是 `live`（2026-11-19）；两个 Horizon 模型都没有 provider（2026-11-20）。

## 附录 · Source discussion（原文）

Owner 关于情绪数据怎么进画面的讨论，按原文保留。

> 那这边我有个问题，拿到的情绪的数据好像在这用不大上？prompt已经把风格固定好了？假如我给你一篇日记的28种情绪概率分布，这个和提取的意向词语配合能不能出一副更细腻一些的画呢

能。情绪数据在画里的位置就在这儿：风格段决定"谁在画"，意象决定"画什么"，情绪分布决定"这幅画的温度和天气"。风格固定，不等于整幅画的感觉也固定。你拍的 Nilima 卷轴就是例子：红橙色那幅和淡绿色那幅出自同一个画家、同一套语言，但情绪温度完全不一样。

但 28 维不能直接塞进 prompt

图像模型看不懂 "sadness 0.18" 这种数字，修饰词一多还会互相抵消。中间需要一层翻译：分布 → 少量视觉参数 → 固定写好的短语。分两种用法：

1. 全局氛围：用整篇的分布

给 28 种情绪各配一个固定的 VA 坐标（可以参考 NRC VAD 词典），按概率加权，算出整篇的 V 和 A，再映射成三样东西：

- 光线：清晨、正午、黄昏
- 暖色范围内的冷暖、饱和度
- 画面密度和留白多少

2. 点缀意象：只取 top-3

超过阈值的前三种情绪，各自对应一个小的"情绪点缀"，同样写进意象词典。比如：

- sadness / grief → 飘落的叶子，局部颜色变淡
- nervousness / fear → 小框排得更挤，人物更小
- anger / annoyance → 一点朱红，纹样边缘更尖
- caring / love / gratitude → 暖灯、金色纹样、开着的花
- optimism / relief → 画外延伸的小路，地平线上的晨光
- confusion → 分岔、绕弯的小路
- realization → 一扇亮起来的窗

最好按情绪段给分布

如果整篇只有一个分布，日记里的起伏会被抹平。能拿到每个情绪段的分布的话，卷轴每个区域单独调：顶部可以是淡的、雾蒙蒙的，底部是暖的、亮的。画面的细腻感主要就从这里来。

护栏

调节范围要设上下限。悲伤只能让画面变淡、变空、变远，不能变暗。温暖的底线写死在代码里。

用这篇举个例子（分布是假设的）

假设分布是 nervousness 0.22、sadness 0.18、annoyance 0.12、caring 0.10、optimism 0.08，在原来的 prompt 后面会多出这样一段：

```
Late-afternoon light warming toward early evening. Upper half in paler, quieter washes, a fine stippled drizzle over the distant city. The task patches sit slightly tighter together, a few falling leaves drifting between them. A tiny touch of vermilion along the window frame. Small blossoms opening around the embracing figures. At the bottom edge, first light on the horizon where the path leaves the frame.
```

（意思是：午后渐入黄昏的光；上半部分颜色更淡、更安静，远处的城上飘着细密的点状小雨；事务小框挨得更紧，中间飘着几片落叶；窗框上一点朱红；相拥的人物周围开出小花；最底下小路伸出画外的地方，地平线上有一点晨光。）

另外要提醒一点：28 类的标签体系（GoEmotions）来自英文 Reddit 评论，直接用在中文日记上会有噪声。只取 top-3 加阈值，能过滤掉一部分噪声。

> 所以氛围本身是靠llm分析情绪分布生成的？这一步是不是配合原文一起喂给llm然后直接一起做出出图需要的东西比如氛围，点缀意向？我现在的设想是对我的长日记分段，每段都有这个情绪分布，然后结果可以做情绪分布图饼图，然后这些丢给llm，确定情绪流向，每一段的氛围点缀，确定出图的方向？然后再用固定风格的prompt + llm给的结果给图像生成模型？

你的设想大方向是对的，只有一处要调整：我上一条说的氛围不是 LLM 生成的，是代码查表算出来的。

原因还是前面那个问题。情绪分布本身是稳定的数字，如果再交给 LLM 自由发挥成一段氛围描述，同一组数字每次会被写成不同的样子，稳定性就丢了。查表的好处是：同样的分布永远出同样的氛围，好调试，而且那张映射表是你按自己的审美手调的。

修改后的管线

1. 分段（规则）：按自然段切，太短的段并进相邻段。分类器在段落长度的文本上效果最好。
2. 每段打分（分类器，确定性）：得到 28 维分布，存库、画图。
3. 数字翻译成视觉（代码，确定性）：每段分布算出 VA 和 top-3，查表得到氛围参数（光线、冷暖、密度）和点缀候选 ID。
4. LLM 只做结构判断，并且只能做选择：输入是原文、每段的 VA 和 top-3、候选列表；输出结构化的 ID：
   - 把多个段落合并成 4–6 个情绪段，对应卷轴的几个区域
   - 判断情绪流向和转折点，决定哪一段放中心
   - 每段的主意象：从意象词典里选
   - 每段的点缀：从第 3 步给出的候选里挑
   - 挑写进画里的原句
5. 拼 prompt（代码）：固定风格段 + 区域模板 + 氛围短语 + 点缀短语，然后出图。
6. 人工确认（可选）：出图前看一眼第 4 步的结果，不满意可以换。

分工的逻辑是：理解叙事的事交给 LLM，比如哪段是转折、哪几段该合并、意象怎么对应原文，这些规则写不出来；把数字翻译成画面的事交给代码，这些规则写得出来，也应该由你来定。

关于图表

饼图能看清单段内部的情绪构成，但看不出顺序。想看"情绪流向"，用堆叠面积图更合适：横轴是段落顺序，每种情绪是一条色带，起伏一眼就能看出来，而且它的形状本身就很像一条卷轴。两种图可以都做，饼图用来点开看单段的细节。
