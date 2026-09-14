# L2 生成层评测报告

- 语料目录：`eval\fixtures\synthetic\pdf`
- 模型：deepseek-flash（deepseek-flash @ https://api.deepseek.com）
- 样本：30 条（可评测 26，no_answer 4）
- LLM-as-judge：开启

> ⚠️ 生成层有随机性（temperature > 0），同一份 golden set 两次结果不会逐字相同；
> 引用/拒答的数字应看**量级与分层**，不要当成精确常数。

## 一、引用准确率

| 指标 | 值 | 口径 |
|---|---|---|
| 引用精确率 | **36.2%** | 答案 `[来源 N]` 指到的来源中，属于期望来源的比例 |
| 引用召回率 | **93.5%** | 期望来源里被答案正文引用到的比例 |
| 文档命中率 | **92.5%** | 答案引用的来源落在期望**文档**里的比例（只看文档、不看页） |
| 至少引到一个期望页 | **100.0%** | 引用的页里至少有一个是标准答案页的条目占比 |

| 答案带来源标记的题数 | 26 / 26 | 完全没写 `[来源 N]` 的答案不进精确率分母 |

> **口径**：统计的是答案**正文里写的** `[来源 N]`，不是 `source_context` ——
> 后者是 top_k 条检索上下文，拿它算精确率会把「检索多给了几条」记成「回答引错了」。
> `[来源 N]` 与 `sources[N-1]` 一一对应（`ContextBuilder.render()` 的 1-based 标记）。

### 偏差构成（回答「精确率低是口径窄还是真引错」）

| 类型 | 条数 | 读法 |
|---|---|---|
| 同文档、页不同 | 24 | 内容相邻的页，多半是期望页集合偏窄（口径问题） |
| 文档不同 | 0 | 更可能是真的引用偏差 |

| 条目 | 答案引到的来源 | 期望来源 | 类型 |
|---|---|---|---|
| `syn001` | 00-introduction-ia.pdf p2、00-introduction-ia.pdf p21 | 00-introduction-ia.pdf p2 | 同文档，页不同 |
| `syn002` | 00-introduction-ia.pdf p8、00-introduction-ia.pdf p9 | 00-introduction-ia.pdf p9 | 同文档，页不同 |
| `syn003` | 00-introduction-ia.pdf p9、00-introduction-ia.pdf p10 | 00-introduction-ia.pdf p10 | 同文档，页不同 |
| `syn004` | 00-introduction-ia.pdf p7、00-introduction-ia.pdf p8 | 00-introduction-ia.pdf p7 | 同文档，页不同 |
| `syn005` | 00-introduction-ia.pdf p2、00-introduction-ia.pdf p14 | 00-introduction-ia.pdf p14 | 同文档，页不同 |
| `syn006` | 01-recherche-et-planification.pdf p6、01-recherche-et-planification.pdf p24、01-recherche-et-planification.pdf p25 | 01-recherche-et-planification.pdf p6 | 同文档，页不同 |
| `syn007` | 01-recherche-et-planification.pdf p9、01-recherche-et-planification.pdf p10、01-recherche-et-planification.pdf p13 | 01-recherche-et-planification.pdf p10 | 同文档，页不同 |
| `syn008` | 01-recherche-et-planification.pdf p13、01-recherche-et-planification.pdf p17、01-recherche-et-planification.pdf p24 | 01-recherche-et-planification.pdf p17 | 同文档，页不同 |
| `syn009` | 02-logique-et-satisfaisabilite.pdf p8、02-logique-et-satisfaisabilite.pdf p9、02-logique-et-satisfaisabilite.pdf p16、02-logique-et-satisfaisabilite.pdf p22、02-logique-et-satisfaisabilite.pdf p24 | 02-logique-et-satisfaisabilite.pdf p8 | 同文档，页不同 |
| `syn010` | 02-logique-et-satisfaisabilite.pdf p9、02-logique-et-satisfaisabilite.pdf p24 | 02-logique-et-satisfaisabilite.pdf p9 | 同文档，页不同 |


## 二、拒答（两种口径对比）

| 指标 | 启发式 | LLM-as-judge |
|---|---|---|
| no_answer 拒答正确率 | 75.0% | 75.0% |
| 可评测题误拒率 | 0.0% | 0.0% |

两种口径在 30 条可比样本上**分歧 0 条**（0.0%）。分歧越大，越说明单靠启发式不可靠 —— 这本身就是一条结论。

## 三、工具循环（回答假设 #11）

| 指标 | 值 |
|---|---|
| 发生过工具调用的题数 | 6 / 30 |
| 工具调用总次数 | 12 |
| 工具调用失败次数 | 0 |

> 工具调用次数为 0 不一定意味着「没触发工具循环」——也可能是模型直接放弃了调用，或工具失败后降级直答。

## 四、延迟与成本（回答假设 #9）

| 指标 | 值 |
|---|---|
| 端到端延迟 P50 | 5642 ms |
| 端到端延迟 P95 | 11318 ms |
| 输入 token 平均 | 3457 |
| 输出 token 平均 | 513 |

> 延迟是**不含流式**的整段等待（从提问到拿到完整回答），与首字延迟 TTFT 不是一回事。

## 五、失败案例

没有执行失败的样本。

## 六、限制

1. 样本 30 条，且 query 由项目作者构造（有「照着目录出题」的偏易倾向）；
2. 生成层有随机性，跨次比较需谨慎；
3. 引用口径只看「引用到的页是否在期望页内」，**没有**判定「答案的每句话都被引用支持」（faithfulness）——那需要更细的 judge，见 planning/10；
4. 拒答的启发式口径依赖措辞，judge 口径依赖模型自身判断，两者都非金标准。
