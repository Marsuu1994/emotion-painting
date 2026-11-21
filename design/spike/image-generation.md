# Spike: Image generation — 出图

**Status: awaiting owner review** · 2026-11-21 · PR #8 · 回答 `../overall-design.md` 的 open question 2（image channel）和 5（quote lines 写进画里用什么语言）· 来源：diary → painting handoff（2026-11-19：风格、`style-reference.jpg` 用 Gemini 出的图）、本 session 对 Pollinations 的实测 · 相关：`imagery-layer.md`（prompt 怎么拼）

> 语言约定：叙述用中文；服务名、模型 id 和代码标识保留英文（Pollinations、`sana`、`gemini-3.1-flash-image-preview`、`seed` …），和代码、`overall-design.md` 一一对应。

## Trigger · 起因

要 e2e 跑通，最后一步是出图。`overall-design.md` 原来写的是「Pollinations 匿名调用，返回 Flux 的图」。2026-11-21 实测，这个前提已经不成立了：

| 实测（匿名，`image.pollinations.ai`） | 结果 |
| --- | --- |
| 实际用的模型 | 响应头 `x-model-used: sana`；`/models` 只列 `["sana"]`；请求里写 `model=flux` 被忽略 |
| 频率 | 每个 IP 每 45 秒 1 张；超了返回 `402 FREE_LIMIT`，带 `retry-after` |
| 尺寸 | `width=512&height=1024` 有效，出来是竖图 |
| 长 prompt | 1,575 字的 prompt（URL 2,221 字符）正常返回 |
| 同一个 URL 再请求 | 命中缓存，字节完全一样；`seed` 固定时可复现 |
| 水印 | `nologo=true` 对匿名请求无效，右下角有 pollinations.ai 的 logo |
| 质量 | 一张试图：风格段大致对，但细节和 owner 认可的 `style-reference.jpg`（Gemini 出的）差很多 |

所以出图这一环要重新选，另外还有一个之前没发现的缺口：**quote lines 是中文原文**，大多数图像模型写不对中文。

## 选项 · Options：出图服务

| 选项 | 模型 | 费用 | 好处 | 代价 |
| --- | --- | --- | --- | --- |
| A · Pollinations 匿名 | `sana` | 免费 | 不用账号、不用 key；e2e 立刻能跑 | 质量一般；有水印；每 45 秒 1 张，连续调试要等 |
| B · Pollinations + pollen key | 可选 `flux`、`gptimage` 等（在 key 上限定模型） | 按 Pollen 计费，约 $1 = 1 Pollen；每张的价格在 `/image/models` 里，没核实 | 同一个接口，只多一个 key；去掉频率限制和水印（官方说法） | 要注册充值；单价没查实 |
| C · Gemini（`gemini-3.1-flash-image-preview`，即 Nano Banana 2） | Gemini 图像模型 | 没有免费额度；512px 约 $0.045/张，1K 约 $0.067/张；每张参考图约 1,120 input token | **能附参考图锁风格**（handoff 里定的「match the style of this image」）；owner 认可的那张就是它出的；写字准 | 要 Google 账号和 API key；新 SDK、新依赖；preview 模型 |
| D · HF Inference Providers 上的 FLUX（fal-ai 等） | `FLUX.1-schnell` 等 | 扣 HF 账户的 inference credits | 和 Endpoint 同一个 HF 账号 | 每个 provider 请求格式不同（原 open question 2）；不能附参考图 |

**Phase 1 默认：A。** 先让 e2e 跑通，不需要任何账号；代码遇到 `402` 按 `retry-after` 等一次。出图接口做成可替换的（输入 prompt、尺寸、seed，输出图片字节），换 B、C、D 只换这一层。

## 选项 · Options：quote lines 写进画里

| 选项 | 做法 | 好处 | 代价 |
| --- | --- | --- | --- |
| a · 不写字 | quote lines 只存进 metadata，不进 prompt | 最简单；不会写错字 | 少了 Nilima 那种「诗句写进画里」的效果 |
| b · LLM 给英文版 | LLM 输出每句的英文版，prompt 里用英文 | 英文大多数模型写得对 | 不是原话；`sana` 写英文也不稳 |
| c · 出图后由代码叠字 | 用代码把中文原句画到图上（固定字体、位置） | 一定是对的中文，原话 | 多一个图片处理依赖；字和画是分开的两层，不像画里本来就有 |
| d · 交给能写中文的模型 | 选 C（Gemini），prompt 里直接放中文 | 一体 | 绑定 C；中文仍可能出错 |

**Phase 1 默认：a。** 先不写字，quote lines 照样由 LLM 挑、存下来。

## 待拍板 · Open questions

1. **出图服务**：A、B、C、D 选哪个？Phase 1 先用 A。
2. **Quote lines**：a、b、c、d 选哪个？Phase 1 先用 a。
3. **尺寸和 seed**：竖图 512×1024 够不够；`seed` 固定（同一篇日记重跑出同一张图，前提是 prompt 不变）还是每次随机。Phase 1 默认 512×1024、seed 固定为一个常量。
4. **参考图**：如果选 C，`style-reference.jpg` 放进 repo 当固定参考图吗？

## 批准之后 · After this

答案写进「已定的事」，标 `Status: decided`，把 `overall-design.md` 的 Step 4 改成定下来的服务；实现完成后移到 `archived/`。

## Sources

- 2026-11-21 实测：`image.pollinations.ai/prompt/...` 的响应头（`x-model-used`、`x-auth-status`）和 `402 FREE_LIMIT` 的响应体；`image.pollinations.ai/models`。
- [Pollinations API docs (APIDOCS.md)](https://github.com/pollinations/pollinations/blob/master/APIDOCS.md)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini 3.1 Flash Image (Vertex AI docs)](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-1-flash-image)
- [Gemini 3.1 Flash Image pricing discrepancy (forum)](https://discuss.ai.google.dev/t/gemini-3-1-flash-image-preview-inconsistent-pricing-between-ai-studio-and-api-docs/127608)
