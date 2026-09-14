# eval —— L1 检索层评测

> 设计依据：[`planning/10-评测集与ProductDoc设计.md`](../planning/10-评测集与ProductDoc设计.md) §1
> 最新结果：[`docs/eval-report-golden.md`](../docs/eval-report-golden.md)

## 为什么把评测拆成两层

| 层 | 测什么 | 要 LLM 吗 | 成本 | 可重复性 |
|---|---|---|---|---|
| **L1 检索层** | 能不能把**正确的片段**召回到前 k 条 | ❌ | **0** | ✅ 完全确定性 |
| L2 生成层 | 引用准确率、拒答正确率、回答可用率 | ✅ | 低 | ⚠️ 有随机性 |

**L1 完全离线可重复**，所以每次改切块 / 换模型 / 调 `top_k`，都能立刻零成本看到命中率变化。
这正是回答"要不要做章节树切块"（`planning/08` §2.3）唯一有说服力的方式。

L2 生成层评测是 [`run_eval_l2.py`](run_eval_l2.py)：引用准确率 / 拒答正确率（两种口径对比）/
工具循环统计 / 延迟与 token 成本。**需要先在界面「设置」里配好并激活一个模型** ——
没有激活配置时它会明确报错退出，不会静默跑出一份空报告。见下方「L2 怎么跑」。

## 怎么跑

```bash
# 在仓库根目录
python eval/run_eval.py --docs-dir "D:/桌面/测试文件"

# 输出 Markdown 报告
python eval/run_eval.py --docs-dir "D:/桌面/测试文件" --out docs/eval-report-golden.md
```

脚本会：建一个**临时库** → 用**生产链路**（真解析 → 真切块 → 真嵌入）摄取 `--docs-dir` 下全部 PDF
→ 逐条检索 → 出报告 → 删掉临时库。**不碰 `data/`**，也不会留下中间产物。

首次运行要下载/加载 embedding 模型（e5-large 约 2.2 GB）；之后每次约 2 分钟（290 页语料）。

### CI 门禁（小型冒烟集，每 push 跑）

```bash
python eval/run_eval.py --docs-dir eval/fixtures/pdf \
  --golden-set eval/golden_set_ci.jsonl --gate-hit-rate-5 0.6
```

- `--gate-hit-rate-5 FLOAT`：门禁模式 —— 评测集自检失败 **exit 2**；HitRate@5 低于阈值 **exit 1**；否则 exit 0。不传该参数时行为不变（只出报告）。
- CI 的 `eval-gate` job（`.github/workflows/quality.yml`）每次 push 用真 e5-large 跑上面这条命令，模型目录走 `actions/cache` 缓存。
- `eval/fixtures/pdf/ci_corpus.pdf` + `eval/golden_set_ci.jsonl` 是提交在仓库里的小型冒烟集（3 条可评测 + 1 条 no_answer）：只拦"检索链路彻底坏了"这类接线级回归；**全量 46 条的质量结论仍需要你的私人语料**——但**别人可复现**的那部分改由自产合成语料承担（见下方「公开基线」与「L2 怎么跑」）。

### 公开基线（自产合成语料，可随仓库分发）

```bash
python eval/run_eval.py --docs-dir eval/fixtures/synthetic/pdf \
  --golden-set eval/golden_set_synthetic.jsonl
```

私人语料上的那份结论（46 条）**别人复现不了** —— 课件有著作权，不随仓库分发、也不该出现在
公开录屏里。所以另有一套**完全自产**的合成语料（`eval/fixtures/synthetic/`，
生成脚本 `scripts/make_synthetic_corpus.py`）承担两件事：demo 的演示文档、以及**别人 clone 后能自己跑出来**的公开基线。

- 当前结果：26 条可评测 **HitRate@5 92.3%**、@10 100%、@1 76.9%、MRR 0.850 —— 见 `docs/eval-report-synthetic.md`。
  语料是**六份讲义 / 154 页 / 189 个片段**，`top_k=20` 因此只覆盖 10.6% 的语料，并且有两条真实的
  失败案例（`syn006` 八数码启发式、`syn013` 随机森林），不再是一片满分。
- ⚠️ **它与私人语料那套不可直接比较**：合成语料排版整齐、没有图表页、没有 OCR 噪声，天然好检索；
  私人语料则是 5 份文档 / 408 个片段，`top_k=20` 覆盖 4.9%。两份报告是两套口径，各自独立陈述，
  不要把差距解释成"优化收益"。
- ⚠️ 合成语料的局限（`no_answer` 只验证了"语料里没有"）见
  [`fixtures/synthetic/README.md`](fixtures/synthetic/README.md)。

## L2 怎么跑（需要 LLM provider）

```bash
# 先启动前后端，在界面「设置」里填好并激活一个 OpenAI 兼容模型
python eval/run_eval_l2.py --docs-dir "D:/桌面/测试文件" --out docs/eval-report-l2.md
python eval/run_eval_l2.py --docs-dir "D:/桌面/测试文件" --limit 5   # 小样本试跑
python eval/run_eval_l2.py --docs-dir "D:/桌面/测试文件" --no-judge  # 跳过 LLM-as-judge
```

与 L1 的区别：L2 走**完整问答链路**（路由 → 检索 → Agent（含有界工具循环）→ 带来源回答），
所以**有 LLM 成本**、结果也**有随机性**；它复用同一份 golden set 与同一套语料摄取逻辑，
只是把"检索完就停"改成"一路答完并观测"。

拒答判定同时用**启发式**（拒答措辞）与 **LLM-as-judge** 两种口径，并报告两者的分歧率 ——
"口径本身可不可信"也是结论的一部分。

### L2 的两套语料（口径不同，各自独立陈述）

| 语料 | 条数 | 带 `[来源 N]` | 引用召回率 | 文档命中率 | 端到端 P50 | 报告 |
|---|---|---|---|---|---|---|
| 私人（**不可分发**） | 46（40 可评测 + 6 拒答） | 40 / 40 | 77.8% | 89.9% | 5.5 s | `docs/eval-report-l2.md` |
| 自产合成（**可分发**） | 30（26 可评测 + 4 拒答） | 26 / 26 | 93.5% | 92.5% | 5.6 s | `docs/eval-report-l2-synthetic.md` |

合成语料那份别人 clone 后能自己跑出来（约 **¥0.3**）；跑法与 L1 的公开基线同一套语料：

```bash
python eval/run_eval_l2.py --docs-dir eval/fixtures/synthetic/pdf \
  --golden-set eval/golden_set_synthetic.jsonl --out docs/eval-report-l2-synthetic.md
```

成本与延迟的汇总账本见 [`../docs/cost-and-latency.md`](../docs/cost-and-latency.md)：
单次提问约 **¥0.01**，L2 全量一次 **不到 ¥1**，而 L1 是**零 LLM 成本**。

## golden set 的 schema

`eval/golden_set.jsonl`，一行一条：

| 字段 | 说明 |
|---|---|
| `id` | `q001` … |
| `type` | `fact`（事实查找）/ `cross_page`（跨页综合）/ `terminology`（法语术语）/ `no_answer`（应拒答） |
| `query` | 真实提问，**混入中文、法语、中法混杂三种形态** |
| `expected_sources` | `[{doc, pages}]`：`doc` 是 PDF 文件名，`pages` 是页码数组；`no_answer` 类为空 |
| `expected_keywords` | 用于**自检**：这些词必须真出现在期望页里 |
| `must_not_appear` | 仅 `no_answer` 类：这些词若出现在语料里，说明这题其实有答案 |
| `notes` | 这条想验证什么 |

## 指标定义

- **HitRate@k** = 期望来源出现在前 k 条召回的 query 数 / 可评测 query 数。
  "命中"的判定口径见下方——**口径写清楚和数字本身一样重要**。
- **MRR** = 平均倒数排名，`1/最佳名次` 的均值。它比 HitRate 更敏感：把答案从第 5 名提到第 1 名，
  HitRate@5 不动，MRR 会涨。
- `no_answer` 类**不进** L1 命中率（它们没有期望来源），它们的作用是给 L2 的拒答评测用。

### 判定口径（与本项目的数据模型绑定）

> **命中 = 召回片段里存在「文档名相同 **且** 页码落在 `expected_sources.pages` 内」的一条。**

为什么用页码而不是"关键词出现在片段里"：本项目的 chunk 是按页（`DocumentUnit`）切出来的，
页 ↔ 片段一一对应，所以页码是个**硬条件**。

**这个口径比首测收紧了很多。** 首测的期望片段集合 p50=7、max=26（"沾边就算命中"），
本轮的期望页码集合 p50=3。两次的 HitRate **不可直接比较**——见 §5。

## 两条自检（跑评测时自动执行）

这两条存在的理由，是首轮报告真实栽过的坑：

1. **关键词自检**：每条可评测 query 的 `expected_keywords` 必须真出现在期望页的片段文本里。
   首轮把"关键词根本找不到"当成"未命中"，方向直接测反。
   匹配前做**空白折叠 + 大小写折叠**——PDF 提取的文本会把短语按换行拆开。
2. **no_answer 反查**：用整库文本反查 `must_not_appear`，命中就说明"这题其实有答案"。
   用**词边界**匹配，否则 `ECTS` 会命中 `factuellement incorrects`、`mail` 会命中教师姓氏 `Mailly`。

**本轮自检真的抓到了一条错题**：`q041` 原本问"老师邮箱是多少"，而语料 p3 明确写了
`jean-guy.mailly@ut-capitole.fr` —— 它不是无答案题，已替换。

## 局限（读数字之前先读这一节）

1. **样本仍有限**：46 条（40 可评测 + 6 no_answer）。分类型后的样本更少（`cross_page` 只有 6 条），
   所以**按类型的数字只能当方向看，不要当结论**。
2. **query 由项目作者构造**，可能有"照着目录出题"的偏易倾向。理想的 golden set 应来自
   真实用户提问记录——这一条现在做不到，只能如实承认。
3. **与历史报告的数字不可直接比较**：

   | | 首测 `docs/eval-report.md` | 本轮 `docs/eval-report-golden.md` |
   |---|---|---|
   | query 数 | 12 | 40 |
   | 判定口径 | 关键词包含（期望集合 p50=7） | 文档名 + 页码（集合 p50=3） |
   | `chunk_size` | 500 | **800**（生产默认） |
   | 中文 HitRate@5 | 41.7%–50% | **90.0%** |

   **不得**把这 40 个百分点的差距说成"优化收益"：口径、数据集、切块参数三样都变了。
4. **`no_answer` 只验证了"语料里没有"**，**没有**验证"系统是否真的拒答"——那需要真实 LLM（L2）。
   现在只能说这 6 条**题目本身**是合格的拒答题。

## 怎么新增一条 query

1. 先在语料里找到确切的页码（打开 PDF 或跑一次大纲提取），别凭印象写；
2. 按上面的 schema 追加一行，`expected_keywords` 填**该页里真实出现**的词
   （注意原文拼写，比如这份课件里是 `Random forrest` 而不是 `forêt`）；
3. 跑一次 `run_eval.py`——自检会告诉你关键词是否真的找得到；
4. 如果是 `no_answer` 类，填 `must_not_appear`，反查会告诉你这题是不是其实有答案。

## 与其它文档的关系

| 想知道 | 看 |
|---|---|
| 为什么要分层、指标怎么定 | `planning/10` §1–2 |
| 检索质量的根因诊断与模型对照 | `docs/retrieval-diagnosis.md` |
| 首测（12 条）的结论与方法学教训 | `docs/eval-report.md` |
| 为什么 L1 不用 LLM | `planning/10` §1（"让 L1 完全离线可重复"） |
| 可随仓库分发、别人能复现的公开基线 | `docs/eval-report-synthetic.md`、[`fixtures/synthetic/README.md`](fixtures/synthetic/README.md) |
