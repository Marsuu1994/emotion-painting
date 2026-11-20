# Spike — Measurement Layer

A dated record of how the measurement layer was chosen: the candidates, the one picked, what it costs, and one probe run. It is not kept current — `../overall-design.md` holds the pipeline as it is now.

- **Date:** 2026-11-19
- **Decided:** method 1 — translate the entry to English, score each segment with a 28-label emotion classifier, compute valence and arousal from that distribution with our own coordinate table.
- **Next:** imagery extraction and the dynamic prompt (§8), not decided.

## 1. The Question

What turns a diary segment into emotion numbers, and what those numbers have to be for the painting downstream.

## 2. Constraints (from the owner)

- **Segment where the emotion turns.** In the owner's writing that is a newline. Entries without newlines (34 of the 36 existing dumps) fall back to sentences packed into segments of about 200–300 characters.
- **A fixed model, not an LLM.** The same text always gets the same numbers; every output records the model id and revision.
- **Hosted inference** (Hugging Face or similar), not local. Privacy is out of scope for now.
- **Clear licences**, open models already on the Hub — no weights whose terms need asking about.
- **Accuracy doesn't matter yet.** Get the data flowing first.
- **Known weakness to design around:** emotion that depends on earlier context — a reference back, a reversal, comfort that only makes sense after the struggle.

## 3. How the Design Was Reached

Two passes: forward from the text, to see what can be measured at all; then backward from the painting, to see what the measurement has to deliver.

### Forward — from the text

1. **An LLM scoring each entry** was the first idea, and was dropped: its numbers drift between runs, and current Claude models take no `temperature`, so drift can't be turned down. Open-weight LLMs at temperature 0 are still not bit-for-bit reproducible under batched GPU inference.
2. **Fixed models.** A search of the Hub found no Chinese valence/arousal model, and the Chinese emotion classifiers score modestly (vendor-reported macro-F1 0.44–0.56 on Chinese social media).
3. **Train a head ourselves** on a frozen embedding (BRIGHTER Chinese, CC-BY-4.0) — dropped by the owner: no training.
4. **Translate, then use English resources.** English has direct V/A models, but the one on the Hub (`BenRongey/deberta-v3-base-emobank-vad`) is a personal upload with an auto-generated card.
5. **Mendes & Martins (ECIR 2023)**, a peer-reviewed multilingual V/A model trained on Chinese data too — the most citable, dropped: the weights carry no licence and the training data includes research-only sets.
6. **Licence-clean, hosted, today** left three routes (§4), and method 1 was picked.

### Backward — from the painting

Start from the image prompt (the style discussion in the diary → painting handoff) and ask what each part of it needs:

| Prompt part | Decides | Needs from measurement |
| --- | --- | --- |
| Style block | who paints | nothing — fixed |
| Regions of the vertical scroll, top to bottom | the entry's arc | segments **in order** |
| Centre figure | the turning point | a valence sequence to find the turn in |
| Atmosphere per region (light, warmth, density) | temperature and weather | **V and A** per segment |
| Accents per region (falling leaves, a touch of vermilion, a lit window) | texture | **the top emotions, by name, with scores**, per segment |
| Main motif per region | what is painted | the text, read for its narrative (§8) |

So the measurement layer has to deliver, per segment and in order, **a full distribution over named emotions plus a V/A point**. A model that outputs only V/A (Mendes & Martins, the EmoBank DeBERTa) serves the atmosphere but not the accents. A distribution serves both, because V/A can be computed from it. That is why method 1 fits beyond its licences: it is the only hosted candidate whose output covers every row above.

## 4. Candidates

| Candidate | Output | Chinese | Served today | Licence | Verdict |
| --- | --- | --- | --- | --- | --- |
| LLM structured scoring | anything asked | yes | yes | — | dropped: not reproducible |
| `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, zero-shot (the previous Phase 1 default) | entailment score per label we write | yes | hf-inference | MIT | replaced: scores depend on how we word each label, and the vocabulary is ours to invent rather than a published one with circumplex positions |
| `MilaNLProc/xlm-emo-t` | 4 emotions | yes | hf-inference | depends on source datasets | too coarse for accents |
| `tabularisai/multilingual-emotion-classification` | 11 emotions | yes | hf-inference | MIT on the Hub, NC elsewhere | licence unclear |
| `BenRongey/deberta-v3-base-emobank-vad` | V, A, D | after translation | no — needs an endpoint | MIT (EmoBank CC-BY-SA 4.0) | weak model card; no distribution |
| Mendes & Martins, XLM-R-large | V, A | yes | no — self-host | code MIT, weights none | dropped: licence |
| `Horizon-Labs/multilingual-emotions-base` / `-small` | the same 28 GoEmotions labels | yes | no — needs an endpoint | Apache-2.0 | **the upgrade path**: drops translation, same labels |
| **Method 1:** `Helsinki-NLP/opus-mt-zh-en` → `SamLowe/roberta-base-go_emotions` | 28 GoEmotions labels | after translation | **both on hf-inference** | CC-BY-4.0 → MIT (GoEmotions Apache-2.0) | **chosen** |

## 5. Decision — Method 1

1. **Segment** (rules): at newlines; a long block without one is packed sentence by sentence into ~200–300 characters; a very short tail joins its neighbour.
2. **Translate** each segment in **units of up to about 40 characters** with `Helsinki-NLP/opus-mt-zh-en` (beam search, 6 beams, from the model's own generation config), and join the results. The 40 is not the model's limit — it reads up to 512 tokens, and the longest segment here was 144 — but a provisional setting from one entry: the largest size at which, with the caps on, no unit lost content (§7). The units come from rules, not a model — the owner's writing runs on commas rather than full stops, so the comma serves as the clause boundary:
   - cut first at hard boundaries: newlines and `。！？!?…；`;
   - a piece still over the limit is cut into clauses at soft boundaries (`，、：—`), and the clauses are packed back together up to the limit; English words are never cut;
   - generation is capped: no repeated 3-word sequence, and an output length bound by the input's length;
   - a unit of 10 or more characters whose English word count per source unit (a Chinese character, or an English word as one) falls below about 0.3 has dropped content, and is cut finer and translated again; one above about 1.2 has looped past the cap, and is flagged in the output. The check catches a unit that lost most of itself, not a long unit that lost only its last clause.

   Why units of this size, and not whole segments or single clauses: §7.
3. **Classify** the English segment with `SamLowe/roberta-base-go_emotions`: 28 independent sigmoid scores (27 emotions and `neutral`, multi-label).
4. **Normalise** the 28 scores to sum to 1 — the distribution the charts and the accents use. The raw scores are kept too.
5. **V/A** = the distribution-weighted mean of a fixed coordinate table: each label has one (V, A) point in [−1, 1], `neutral` at the origin.

Stored per segment: the source text, its translation, the raw scores, the distribution, V, A, both model ids with their revisions, and the coordinate table's version.

Attribution: CC-BY-4.0 (the translator) asks for credit; MIT and Apache-2.0 keep their notices. Listing them in the project's docs is enough.

## 6. Trade-offs

### V/A is computed, not measured

- **It is only as good as the table.** The model names emotions; where each name sits on the circumplex is our call. Change the table and every V/A changes, so the table carries a version.
- **A mixed segment averages toward the centre.** Half sadness and half joy lands near (0, 0) — the same point as neutral. The point loses the mixture; the stored distribution keeps it, and a spread or ambivalence measure can recover it later (the evaluative space model; Griffin's index, (P+N)/2 − |P−N|).
- **Where the coordinates come from:**
  - Written by us from the positions in Russell (1980) — no licence question; the default. A provisional v0 is below, for the owner to tune.
  - NRC-VAD — the earlier discussion suggested it, but its terms are non-commercial and forbid redistribution, and its values would ship inside our table.
  - Warriner et al. (2013) norms — licence not checked.
- **Normalising is a choice too.** The 28 sigmoid scores are independent and don't sum to 1 (0.95–1.76 in the probe). Normalising makes segments comparable but hides how strongly the model fired overall; `neutral` at the origin pulls every point toward the centre in proportion to its score.

Provisional table v0 (V, A):

| | | | |
| --- | --- | --- | --- |
| admiration 0.6, 0.3 | amusement 0.7, 0.5 | anger −0.7, 0.7 | annoyance −0.5, 0.4 |
| approval 0.5, 0.1 | caring 0.6, 0.0 | confusion −0.3, 0.3 | curiosity 0.3, 0.4 |
| desire 0.4, 0.5 | disappointment −0.6, −0.3 | disapproval −0.5, 0.2 | disgust −0.7, 0.4 |
| embarrassment −0.5, 0.4 | excitement 0.7, 0.8 | fear −0.7, 0.7 | gratitude 0.7, 0.1 |
| grief −0.8, −0.4 | joy 0.8, 0.5 | love 0.8, 0.3 | nervousness −0.5, 0.6 |
| optimism 0.6, 0.3 | pride 0.6, 0.4 | realization 0.1, 0.3 | relief 0.5, −0.4 |
| remorse −0.6, −0.2 | sadness −0.7, −0.4 | surprise 0.2, 0.7 | neutral 0, 0 |

### Translation

- **Translate-test is the standard cross-lingual route**, and translation drift is accepted for the POC.
- **Local words don't survive.** The translator learned from general parallel text and has nothing for 套瓷 (writing to a prospective supervisor before applying): it came back as "put on the china", and once as an unrelated explicit word. Names and typos go the same way: a friend's name became "a bear"; 幸苦 for 辛苦 turned "you've worked so hard" into "you're so lucky". The classifier reacts mostly to the emotional words around such a word, so a garbled noun costs little — but a typo inside the emotional phrase itself changes the reading.
  - **A possible fix, not adopted**: a glossary the owner keeps, replacing such words with plain Chinese before translation, by rule. In the probe 去联系教授 came back as "contact the professor", 去给教授发邮件 as "e-mail the professor", and a name replaced by 朋友 as "friends". Replacing with English instead made it worse: an English phrase inside the Chinese sentence garbled the whole sentence. The costs: one more table to keep, and it only covers words someone has noticed.
- **Long and short inputs fail differently.** A long input loses its last sentences without warning; a short or repetitive one loops or invents text ("omg" became "I don't know what you're talking about"). English words inside Chinese sentences pass through.
- **Granularity changes the measurement.** Across eight unit sizes, segment 2's V ranged from −0.30 to +0.34, while the other two segments moved much less (−0.17 to −0.36; +0.28 to +0.41) (§7). A segment that mixes four turns is fragile at any unit size: the steady fix for it is segmentation at newlines, not the unit. Units also mean more calls: one per unit, unless the provider takes a batch.
- **Why the output is capped.** A looping translation isn't bounded by its input: it can run up to the model's 512-token maximum (in the probe, 46 "no"s for 40 characters). That costs three ways: the loop reaches the classifier as if the writer had said it; a long enough loop pushes the segment's real sentences past the classifier's own 512-token limit, where they are cut off; and hf-inference bills compute time, which a loop spends. The no-repeat rule stops the loop itself; the length bound (1.5 output tokens per source character, plus 8) is the backstop for a loop the rule misses, set so a normal translation never reaches it — no unit reached it in the probe. The costs: the no-repeat rule also suppresses repetition the writer meant (痛苦痛苦痛苦 becomes "pain and suffering"), and whether hf-inference accepts either as a request parameter is not verified.
- **The way out is a model swap**: `Horizon-Labs/multilingual-emotions-*` reads Chinese with the same 28 labels, so the table and everything downstream stay. It needs an Inference Endpoint.

### The label set comes from English Reddit

- GoEmotions is 58k English Reddit comments, labelled by raters reading them: it measures emotion **as a reader perceives it**, not as the writer felt it.
- A diary is neither Reddit nor English. The top labels carry noise; taking only the top 3 above a threshold (§8) filters part of it.
- Both models read at most 512 tokens; a 200–300-character segment is well inside that.

### Context

The classifier sees one segment at a time, so comfort that only makes sense after the struggle is scored on its own words. Newline segmentation keeps each segment's emotion mostly uniform, which removes most of the within-segment problem; across segments, the arc is read later by the narrative step (§8), not by the measurement.

### Reproducibility

- Two local runs gave byte-identical output.
- Hosted, the provider serves the repository's current revision: if the author updates a model, the numbers change. Each output records the revision so a change is visible. Whether the provider's hardware reproduces local scores to the last digit is not verified.

### Access and cost

Both models are live on hf-inference, so nothing is hosted by us. Calling them needs a Hugging Face token with Inference Providers permission and credits: hf-inference bills compute time; free accounts get no monthly credit, PRO gets $2 a month (overall design, open question 1).

## 7. Probe Run (2026-11-19)

One entry from the diary → painting handoff (about 1,260 characters, no newlines), run on CPU in a scratch environment with the same model revisions the provider serves (`opus-mt-zh-en` `cf10909`, `roberta-base-go_emotions` `d750483`). The fallback split it into three segments. The diary text is not reproduced here.

| Segment | Content (paraphrase) | Chars | Translated | Top 3 (normalised) | V | A |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | low for days, outside pressure about money and plans | 180 | whole | curiosity .32, sadness .26, disappointment .14 | −0.20 | 0.06 |
| | | | at `。！？` | curiosity .29, sadness .26, disappointment .17 | −0.23 | 0.04 |
| 2 | overwhelmed by tasks, comforting self, inner critic, anger | 219 | whole | admiration .37, annoyance .19, anger .10 | +0.15 | 0.32 |
| | | | at `。！？` | sadness .38, disappointment .15, curiosity .09 | −0.28 | −0.08 |
| 3 | back to the present, call mum | 56 | whole | approval .70, neutral .15, admiration .04 | +0.41 | 0.11 |

What it shows:

- **The arc comes through**: negative → negative → positive, ending on the entry's landing.
- **Segment 2 is the problem segment.** It holds four turns — overwhelm, self-comfort, the inner critic, anger — because the entry has no newlines to split them. Translated whole, the anger at its end was dropped and "you're the best" dominated (`admiration`); cut at `。！？`, `sadness` dominated. With the owner's newline habit this block would likely be three or four segments.
- **Questions read as `curiosity`.** Rhetorical self-questions ("why is it like this?") score as curiosity, which v0 places at positive valence — an example of the label set misreading a diary.
- **Segment 3 is a short tail** (56 characters); the packing rule should join it to its neighbour.

### Translation unit size

Segment 2 again, with only the translation unit changed and no caps (packing cuts at soft boundaries; the classifier still reads the whole translated segment):

| Unit | Units | V | What went wrong in translation |
| --- | --- | --- | --- |
| whole segment | 1 | +0.15 | the anger at the end gone |
| cut at `。！？` | 3 | −0.28 | the self-comfort inside a 148-character sentence gone |
| packed to ≤ 80 characters | 3 | −0.06 | an 80-character unit came back as one short sentence |
| packed to ≤ 40 characters | 7 | +0.20 | one unit came back as "no, no, no…" 46 times |
| packed to ≤ 20 characters | 13 | −0.11 | — |
| one clause per unit | 24 | −0.30 | 痛苦痛苦痛苦 looped as "the pain" without end; "omg" became "I don't know what you're talking about"; subjects invented |

- **Two failure modes, at opposite ends**: long inputs drop content, short or repetitive ones loop or invent. The ratio of English words to Chinese characters separates them: about 0.4–0.8 when the translation is whole, 0.19 for the dropped unit, 1.15–9.7 for the loops.
- **The generation caps remove the loops.** With no repeated 3-word sequence and the output length bound, the 46 "no"s became "No, the prosecutor's always in judge. Fuck, leave me alone! It's more painful, painful and painful", and the endless "the pain" became "pain and suffering".

The whole entry with the caps on:

| Unit | Units | Flagged as dropped | V, segments 1 / 2 / 3 |
| --- | --- | --- | --- |
| whole segment | 3 | 0 | −0.25 / +0.03 / +0.40 |
| cut at `。！？` | 10 | 0 | −0.23 / +0.34 / +0.40 |
| packed to ≤ 80 characters | 7 | 1 | −0.36 / −0.06 / +0.40 |
| packed to ≤ 60 characters | 9 | 1 | −0.17 / +0.27 / +0.40 |
| packed to ≤ 40 characters | 14 | 0 | −0.31 / −0.06 / +0.40 |
| packed to ≤ 30 characters | 19 | 0 | −0.30 / +0.09 / +0.35 |
| packed to ≤ 20 characters | 29 | 1, false | −0.29 / −0.11 / +0.35 |
| one clause per unit | 48 | 1, false | −0.33 / −0.29 / +0.36 |

- **No loops and no unit reaching the length bound**, at any size.
- **The ratio misses partial losses.** The whole-segment and `。！？` rows flag nothing, yet without caps those same units lost their last sentences (table above).
- **The two false flags** are a clause made mostly of one English word, counted by its letters — hence counting an English word as one unit.
- **Why 40**: ≤ 40 and ≤ 30 both came through clean; 40 means fewer calls and more context per unit, so fewer invented subjects. One entry is thin evidence: the sweep should be re-run on more entries before the number is fixed.

## 8. From the Numbers to the Painting

The backward pass in more detail; source: the discussion in the appendix.

### Three roles

The style block decides **who paints**, the motifs decide **what is painted**, the emotion distribution decides **the painting's temperature and weather**. A fixed style doesn't fix the mood: two of Nilima Sheikh's scrolls share one visual language and still differ completely in emotional temperature.

### The 28 numbers never go into the prompt

An image model can't read "sadness 0.18", and many modifiers cancel each other out. A layer in between translates: distribution → a few visual parameters → fixed, pre-written phrases. All of it is code and tables, not an LLM, so the same distribution always yields the same phrases, and the tables are the owner's to tune.

- **Atmosphere — from V and A.**
  - light: morning, noon, dusk
  - warmth and saturation, inside a warm range
  - density and how much is left empty
- **Accents — the top 3 emotions above a threshold**, each mapped to a small accent motif in the lexicon:

  | Emotions | Accent |
  | --- | --- |
  | sadness, grief | falling leaves; local colour paling |
  | nervousness, fear | the small frames packed tighter; figures smaller |
  | anger, annoyance | a touch of vermilion; pattern edges sharper |
  | caring, love, gratitude | a warm lamp, gold patterns, open flowers |
  | optimism, relief | a path running out of the frame; first light on the horizon |
  | confusion | a forking, winding path |
  | realization | a window lighting up |

- **Per segment, not per entry.** One distribution for the whole entry flattens its arc; one per segment lets each region of the scroll be tuned on its own — misty and pale at the top, warm and bright at the bottom. Most of the painting's nuance comes from here.
- **Guardrails, in code.** Each parameter has bounds. Sadness can make a region paler, emptier, more distant — never darker. The warm floor is fixed.

### Pipeline, end to end

1. **Segment** (rules).
2. **Score** each segment (fixed models, §5): the 28-label distribution and V/A — stored and charted.
3. **Numbers → visuals** (code, tables): per segment, V/A → atmosphere parameters, top 3 → accent candidate ids.
4. **Narrative structure** (LLM, choosing only): given the source text, each segment's V/A and top 3, and the candidate lists, it returns ids:
   - merge segments into 4–6 emotional beats, one per scroll region
   - find the flow and the turning point, which takes the centre
   - pick each beat's main motif from the motif lexicon
   - pick each beat's accents from step 3's candidates
   - pick the quote lines written into the painting
5. **Assemble the prompt** (code): the fixed style block + region templates + atmosphere phrases + accent phrases; then the image.
6. **Human review** (optional): see step 4's choices before the image is made, and swap any.

The split follows one rule: what needs reading the story — which segment is the turn, which segments belong together, which motif fits the words — goes to the LLM, because no rule can be written for it; what translates numbers into visuals goes to code, because rules can be written for it, and the owner should own them.

### Charts

A pie chart shows one segment's make-up but not the order. For the flow, a stacked area chart: segments along the x-axis, one band per emotion. Its shape already looks like a scroll. Both: the area chart for the entry, a pie on click for one segment.

## 9. Next — Imagery Extraction and the Dynamic Prompt

Not decided. What has to be settled before it is built:

- **The motif lexicon, v1**: one entry per motif — an id, the beat type it serves, whether it is a main motif or an accent, its prompt template. Seeded from the earlier session's examples (`external_pressure`, `task_overload`, `inner_critic`, `anger_release`, `self_compassion`, `return_to_present`, `family_support`, `sealed`).
- **The two tables**: V/A → atmosphere phrases (how many bins on each axis); emotion → accent id, and the threshold.
- **The LLM step's contract**: its inputs and output schema, all ids; validation — every id exists in the lexicon, every quote line is a verbatim substring of the entry; on refusal or a failed schema, the `sealed` motif.
- **Which LLM, and how stable it must be.** It only picks, but the same input can still pick differently; each output records the model and prompt version, and the review step catches the rest.
- **Track B in the overall design** (jieba nouns, rules only): whether the lexicon and the LLM step replace it or sit beside it.
- **Prompt length**: how many regions, accents and quote lines fit before the image model starts dropping parts.

## Sources

- [SamLowe/roberta-base-go_emotions](https://huggingface.co/SamLowe/roberta-base-go_emotions)
- [Helsinki-NLP/opus-mt-zh-en](https://huggingface.co/Helsinki-NLP/opus-mt-zh-en)
- [GoEmotions (Demszky et al., ACL 2020)](https://arxiv.org/abs/2005.00547)
- [GoEmotions dataset](https://huggingface.co/datasets/google-research-datasets/go_emotions)
- [Horizon-Labs/multilingual-emotions-base](https://huggingface.co/Horizon-Labs/multilingual-emotions-base)
- [Mendes & Martins, ECIR 2023](https://arxiv.org/abs/2302.14021)
- [multilingual_va_prediction (README, LICENSE)](https://github.com/gmendes9/multilingual_va_prediction)
- [BenRongey/deberta-v3-base-emobank-vad](https://huggingface.co/BenRongey/deberta-v3-base-emobank-vad)
- [NRC VAD Lexicon — terms of use](https://www.saifmohammad.com/WebPages/nrc-vad.html)
- Russell, J. A. (1980). A circumplex model of affect. *Journal of Personality and Social Psychology*, 39(6), 1161–1178.
- [Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing)
- Hub API (`/api/models/<id>?expand[]=inferenceProviderMapping`), 2026-11-19: both method 1 models `live` on hf-inference.

## Appendix — Source Discussion (verbatim)

The owner's discussion of how the emotion data feeds the painting, kept as written.

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
