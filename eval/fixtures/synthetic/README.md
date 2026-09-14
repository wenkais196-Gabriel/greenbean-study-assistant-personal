# 合成语料（synthetic corpus）

一套**完全自产**的课程文档，用来做 demo 演示与公开的 L1 评测基线。
它不含任何第三方受著作权保护的材料，可以随仓库分发，也可以出现在录屏与截图里。

## 为什么要有它

真实评测语料是法国大学的课程课件 —— 个人学习使用没问题，但它**不能进仓库**，
也不该出现在公开的 demo 录屏里（那是向公众传播别人的作品）。后果是此前所有公开数字
（HitRate@5 90%、L2 引用命中率 89.9%）都建立在私有语料上：**别人 clone 之后一条都复现不了**。

这份合成语料解决的是这件事，而不是替代私有语料上的数字 —— 见下方「已知局限」。

## 怎么生成

```bash
python scripts/make_synthetic_corpus.py            # 生成到本目录
python scripts/make_synthetic_corpus.py --check     # 校验磁盘产物是否与脚本一致
```

内容与生成方式都写在 `scripts/make_synthetic_corpus.py` 里，产物只是它的输出：
改内容要改脚本，再重新生成。`--check` 按**内容**比对（PDF 比每页文本、DOCX/PPTX 比 zip 条目、
PNG 比像素），不一致或缺失就返回非零，所以它能同时回答"产物被手改过吗"与"脚本改了没重新生成"。

> 同一个脚本还负责 **`backend-python/tests/fixtures/pdf/text_two_pages.pdf`** —— 测试用的两页 PDF
> （替换上游带进仓库的那份真实课程作业说明）。一次 `--check` 覆盖全部 5 个产物；产物路径都写在脚本的
> `ARTIFACTS` 表里，相对仓库根。

产物内容可复现：PDF / DOCX / PNG 连字节都一致（PDF 靠固定元数据 + `no_new_id`），
PPTX 的 zip 条目时间戳由 python-pptx 写成"当前时间"，所以只有**内容**保证一致 —— 这也是
`--check` 比内容而不是比字节的原因（字节还会随生成库的版本变化）。

## 产物

| 文件 | 用途 |
|---|---|
| `pdf/00-introduction-ia.pdf` | 21 页导论：定义与子领域、历史、三类范式、应用、伦理、术语表 |
| `pdf/01-recherche-et-planification.pdf` | 25 页：搜索问题建模、非信息搜索、A 星、启发式设计、局部搜索 |
| `pdf/02-logique-et-satisfaisabilite.pdf` | 25 页：命题逻辑、CNF 与 Tseitin、DPLL、现代求解器、CSP |
| `pdf/03-apprentissage-supervise.pdf` | 29 页：模型与损失、树与森林、boosting、SVM、聚类、降维 |
| `pdf/04-evaluation-et-metriques.pdf` | 26 页：数据划分、数据泄漏、交叉验证、过拟合、指标、模型比较 |
| `pdf/05-reseaux-de-neurones.pdf` | 28 页：感知机、反向传播、优化、卷积、循环、注意力 |
| `docx/tp-donnees-et-evaluation.docx` | Word 格式覆盖：demo 里演示多格式上传 |
| `pptx/seance-recherche-arborescente.pptx` | PPT 格式覆盖（1 张 slide = 1 个 `DocumentUnit`） |
| `img/tableau-metriques.png` | 图片格式覆盖：**演示 OCR 需要本机安装 Tesseract**，没装时上传这个文件会失败 |
| `backend-python/tests/fixtures/pdf/text_two_pages.pdf`（路径相对仓库根） | 测试 fixture：**替换掉**上游带进仓库的那份真实课程作业说明；契约见 `tests/integration/document/test_pdf_ingest_pipeline.py` |

六份讲义合计 **154 页 / 189 个片段**（`chunk_size=800`），配 `eval/golden_set_synthetic.jsonl`：
30 条（16 fact / 5 cross_page / 5 terminology / 4 no_answer），**跨 6 份文档分布**，
所以"文档名 + 页码"的判定条件真正起作用。

## 跑一次 L1 评测

```bash
python eval/run_eval.py --docs-dir eval/fixtures/synthetic/pdf \
  --golden-set eval/golden_set_synthetic.jsonl
```

零 LLM 成本，走生产链路（真解析 → 真切块 → 真嵌入）。首次会下载 e5-large（约 2.2 GB）。

## 许可与内容声明

- 本目录内容由本项目生成，随仓库以 MIT 发布，可自由分发、可公开演示。
- 内容全部为**虚构**：虚构校名（Université de démonstration）、虚构教师、虚构邮箱与日期。
- 技术主题只使用公开事实（图灵 1950 年的论文、1956 年 Dartmouth 会议、SAT/CNF、交叉验证等）——
  **事实、算法与术语本身不受著作权保护**（受保护的是表达）。参考文献条目只写书名、作者与年份，
  属于事实性引用。
- ⚠️ **文本由语言模型生成，未经原创性核查，本项目不声称原创性。** 像「一条启发式是可采纳的，
  当它从不估计过高剩余代价」这类定义句属于领域内的惯常表述 —— 抽查确认它与多份公开课程材料
  措辞相近。作为 demo 与评测语料使用没有问题，**不要把它当作原创教材，也不要对外发布为课程
  材料**。

## 已知局限（读数字之前先读这一节）

1. **不能与私有语料上的数字比较。** 合成语料的排版更整齐、没有图表页、没有公式页、没有 OCR
   噪声，天然比真实课件好检索，指标会偏高。更硬的差别在检索深度与语料规模之比：`top_k=20`
   覆盖本语料 `189` 个片段中的 `10.6%`，而私有语料（408 个片段）只有 `4.9%`。
2. **规模仍有限。** 154 页 / 30 条适合做 demo 与"质量趋势"级别的结论，但不足以支撑细粒度结论：
   分类型后样本更少（`cross_page` 5 条、`terminology` 5 条），当前报告里的两条失败案例
   （`syn006`、`syn013`）只说明"存在可分析的失败"，不代表失败率。
3. **合成语料天然缺一类难点。** 全部是排版整齐的纯文本页，没有图表、公式、扫描件与 OCR 噪声 ——
   这些恰恰是真实课件上最容易出错的地方。
4. **`no_answer` 只验证了"语料里没有"**，没有验证"系统是否真的拒答"—— 那需要真实 LLM，
   属于 L2 的职责（见 `eval/README.md`）。

## 与其它文档的关系

| 想知道 | 看 |
|---|---|
| CI 用的那份 6 页冒烟语料 | `eval/fixtures/pdf/ci_corpus.pdf` + `eval/golden_set_ci.jsonl` |
| 评测集 schema、指标定义、判定口径 | `eval/README.md` |
| 私有语料上的全量结果 | `docs/eval-report-golden.md`、`docs/eval-report-l2.md` |
