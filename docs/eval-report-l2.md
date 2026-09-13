# L2 生成层评测报告

- 语料目录：`D:\桌面\测试文件`
- 模型：deepseek-flash（deepseek-flash @ https://api.deepseek.com）
- 样本：46 条（可评测 40，no_answer 6）
- LLM-as-judge：开启

> ⚠️ 生成层有随机性（temperature > 0），同一份 golden set 两次结果不会逐字相同；
> 引用/拒答的数字应看**量级与分层**，不要当成精确常数。

## 一、引用准确率

| 指标 | 值 | 口径 |
|---|---|---|
| 引用精确率 | **41.7%** | 答案 `[来源 N]` 指到的来源中，属于期望来源的比例 |
| 引用召回率 | **77.8%** | 期望来源里被答案正文引用到的比例 |
| 文档命中率 | **89.9%** | 答案引用的来源落在期望**文档**里的比例（只看文档、不看页） |
| 至少引到一个期望页 | **95.0%** | 引用的页里至少有一个是标准答案页的条目占比 |

| 答案带来源标记的题数 | 40 / 40 | 完全没写 `[来源 N]` 的答案不进精确率分母 |

> **口径**：统计的是答案**正文里写的** `[来源 N]`，不是 `source_context` ——
> 后者是 top_k 条检索上下文，拿它算精确率会把「检索多给了几条」记成「回答引错了」。
> `[来源 N]` 与 `sources[N-1]` 一一对应（`ContextBuilder.render()` 的 1-based 标记）。

### 偏差构成（回答「精确率低是口径窄还是真引错」）

| 类型 | 条数 | 读法 |
|---|---|---|
| 同文档、页不同 | 34 | 内容相邻的页，多半是期望页集合偏窄（口径问题） |
| 文档不同 | 0 | 更可能是真的引用偏差 |

| 条目 | 答案引到的来源 | 期望来源 | 类型 |
|---|---|---|---|
| `q002` | 00-Intro-IA.pdf p19、00-Intro-IA.pdf p22 | 00-Intro-IA.pdf p18、00-Intro-IA.pdf p19 | 同文档，页不同 |
| `q003` | 00-Intro-IA.pdf p18、00-Intro-IA.pdf p19、00-Intro-IA.pdf p22 | 00-Intro-IA.pdf p18、00-Intro-IA.pdf p19 | 同文档，页不同 |
| `q004` | 00-Intro-IA.pdf p26、00-Intro-IA.pdf p27、00-Intro-IA.pdf p28 | 00-Intro-IA.pdf p26、00-Intro-IA.pdf p27 | 同文档，页不同 |
| `q005` | 00-Intro-IA.pdf p10、00-Intro-IA.pdf p23 | 00-Intro-IA.pdf p23 | 同文档，页不同 |
| `q006` | 00-Intro-IA.pdf p3、00-Intro-IA.pdf p4、01_Intro ML_compressed.pdf p2、01_Intro ML_compressed.pdf p3 | 00-Intro-IA.pdf p3 | 同文档，页不同 |
| `q007` | 00-Intro-IA.pdf p3、00-Intro-IA.pdf p4、01_Intro ML_compressed.pdf p3 | 00-Intro-IA.pdf p4 | 同文档，页不同 |
| `q008` | 00-Intro-IA.pdf p20、00-Intro-IA.pdf p21、00-Intro-IA.pdf p22、00-Intro-IA.pdf p33 | 00-Intro-IA.pdf p20、00-Intro-IA.pdf p21、00-Intro-IA.pdf p22 | 同文档，页不同 |
| `q009` | 00-Intro-IA.pdf p28、00-Intro-IA.pdf p31、00-Intro-IA.pdf p32、02-SAT-CSP.pdf p5、02-SAT-CSP.pdf p36、02-SAT-CSP.pdf p66 | 00-Intro-IA.pdf p31、00-Intro-IA.pdf p32、02-SAT-CSP.pdf p5 | 同文档，页不同 |
| `q010` | 00-Intro-IA.pdf p11、00-Intro-IA.pdf p14、00-Intro-IA.pdf p26、00-Intro-IA.pdf p27、00-Intro-IA.pdf p33 | 00-Intro-IA.pdf p27、00-Intro-IA.pdf p28 | 同文档，页不同 |
| `q011` | 01-Recherche-Arborescente.pdf p31、01-Recherche-Arborescente.pdf p32、01-Recherche-Arborescente.pdf p37、01-Recherche-Arborescente.pdf p38、01-Recherche-Arborescente.pdf p39、01-Recherche-Arborescente.pdf p41、01-Recherche-Arborescente.pdf p42、01-Recherche-Arborescente.pdf p43 | 01-Recherche-Arborescente.pdf p32、01-Recherche-Arborescente.pdf p37、01-Recherche-Arborescente.pdf p41 | 同文档，页不同 |


## 二、拒答（两种口径对比）

| 指标 | 启发式 | LLM-as-judge |
|---|---|---|
| no_answer 拒答正确率 | 50.0% | 100.0% |
| 可评测题误拒率 | 0.0% | 0.0% |

两种口径在 46 条可比样本上**分歧 3 条**（6.5%）。分歧越大，越说明单靠启发式不可靠 —— 这本身就是一条结论。

## 三、工具循环（回答假设 #11）

| 指标 | 值 |
|---|---|
| 发生过工具调用的题数 | 13 / 46 |
| 工具调用总次数 | 27 |
| 工具调用失败次数 | 0 |

> 工具调用次数为 0 不一定意味着「没触发工具循环」——也可能是模型直接放弃了调用，或工具失败后降级直答。

## 四、延迟与成本（回答假设 #9）

| 指标 | 值 |
|---|---|
| 端到端延迟 P50 | 5468 ms |
| 端到端延迟 P95 | 10602 ms |
| 输入 token 平均 | 4388 |
| 输出 token 平均 | 611 |

> 延迟是**不含流式**的整段等待（从提问到拿到完整回答），与首字延迟 TTFT 不是一回事。

## 五、失败案例

没有执行失败的样本。

## 六、限制

1. 样本 46 条，且 query 由项目作者构造（有「照着目录出题」的偏易倾向）；
2. 生成层有随机性，跨次比较需谨慎；
3. 引用口径只看「引用到的页是否在期望页内」，**没有**判定「答案的每句话都被引用支持」（faithfulness）——那需要更细的 judge，见 planning/10；
4. 拒答的启发式口径依赖措辞，judge 口径依赖模型自身判断，两者都非金标准。
