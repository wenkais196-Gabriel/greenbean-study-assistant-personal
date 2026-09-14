# L1 检索评测报告（golden set）

> 数据集：**30 条**（26 条可评测 + 4 条 no_answer，后者不进 L1 命中率）
> 语料：`eval\fixtures\synthetic\pdf` ｜模型：`intfloat/multilingual-e5-large`（1024 维）｜切块：`chunk_size=800` / `overlap=120`
> 检索深度：`top_k=20`｜命中判定：**文档名 + 页码**同时匹配

## 1. 总览

| 指标 | 值 |
|---|---|
| HitRate@1 | **76.9%** |
| HitRate@3 | **92.3%** |
| HitRate@5 | **92.3%** |
| HitRate@10 | **100.0%** |
| HitRate@20 | **100.0%** |
| MRR | **0.850** |

## 2. 按类型

| 类型 | 条数 | @1 | @3 | @5 | @10 | @20 | MRR |
|---|---|---|---|---|---|---|---|
| fact | 16 | 75% | 88% | 88% | 100% | 100% | 0.819 |
| cross_page | 5 | 60% | 100% | 100% | 100% | 100% | 0.800 |
| terminology | 5 | 100% | 100% | 100% | 100% | 100% | 1.000 |

## 3. 失败案例（HitRate@5 未命中，2 条）

| id | 类型 | 提问 | 期望来源 | 最佳名次 | 实际 top-3 |
|---|---|---|---|---|---|
| syn013 | fact | 随机森林为什么比单棵决策树稳定？ | 03-apprentissage-supervise.pdf p[15] | 6 | 03-apprentissage-supervise.pdf p29；00-introduction-ia.pdf p20；03-apprentissage-supervise.pdf p13 |
| syn006 | fact | 八数码问题里常用什么启发式？ | 01-recherche-et-planification.pdf p[6] | 9 | 02-logique-et-satisfaisabilite.pdf p24；05-reseaux-de-neurones.pdf p6；02-logique-et-satisfaisabilite.pdf p25 |

## 4. 排名分布（全部可评测条目）

| 桶 | 条数 | id |
|---|---|---|
| 第 1 名 | 20 | syn001 syn003 syn004 syn005 syn007 syn008 syn009 syn010 syn011 syn012 syn014 syn015 syn017 syn018 syn020 syn022 syn023 syn024 syn025 syn026 |
| 第 2-5 名 | 4 | syn002 syn016 syn019 syn021 |
| 第 6-20 名 | 2 | syn006 syn013 |
| 未召回 | 0 | — |

## 5. 评测集自检（口径验证）

✅ 每条可评测 query 的 `expected_keywords` 都能在期望页的片段文本里找到。

✅ no_answer 条目未在语料中反查出答案（`must_not_appear` 均未出现）。
