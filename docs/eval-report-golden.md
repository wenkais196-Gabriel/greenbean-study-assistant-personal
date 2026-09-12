# L1 检索评测报告（golden set）

> 数据集：**46 条**（40 条可评测 + 6 条 no_answer，后者不进 L1 命中率）
> 语料：`D:\桌面\测试文件` ｜模型：`intfloat/multilingual-e5-large`（1024 维）｜切块：`chunk_size=800` / `overlap=120`
> 检索深度：`top_k=20`｜命中判定：**文档名 + 页码**同时匹配

## 1. 总览

| 指标 | 值 |
|---|---|
| HitRate@1 | **80.0%** |
| HitRate@3 | **87.5%** |
| HitRate@5 | **90.0%** |
| HitRate@10 | **97.5%** |
| HitRate@20 | **97.5%** |
| MRR | **0.845** |

## 2. 按类型

| 类型 | 条数 | @1 | @3 | @5 | @10 | @20 | MRR |
|---|---|---|---|---|---|---|---|
| fact | 26 | 92% | 92% | 96% | 96% | 96% | 0.931 |
| cross_page | 6 | 50% | 83% | 83% | 100% | 100% | 0.635 |
| terminology | 8 | 62% | 75% | 75% | 100% | 100% | 0.726 |

## 3. 失败案例（HitRate@5 未命中，4 条）

| id | 类型 | 提问 | 期望来源 | 最佳名次 | 实际 top-3 |
|---|---|---|---|---|---|
| q028 | terminology | 什么是 CNF（forme normale conjonctive）？ | 02-SAT-CSP.pdf p[37, 38, 44] | 6 | 02-SAT-CSP.pdf p43；02-SAT-CSP.pdf p42；02-SAT-CSP.pdf p40 |
| q025 | cross_page | 机器学习有哪些典型应用场景？ | 01_Intro ML_compressed.pdf p[9, 10, 11, 12] | 7 | 02_intro supervise_compressed.pdf p42；01_Intro ML_compressed.pdf p8；00-Intro-IA.pdf p25 |
| q037 | terminology | validation croisée（交叉验证）用来干什么？ | 02_intro supervise_compressed.pdf p[14] | 7 | 02_intro supervise_compressed.pdf p10；02_intro supervise_compressed.pdf p13；02_intro supervise_compressed.pdf p42 |
| q024 | fact | 这门课把机器学习分成哪几类？ | 01_Intro ML_compressed.pdf p[19, 20, 21, 22] | 未召回（>20） | 01_Intro ML_compressed.pdf p2；01_Intro ML_compressed.pdf p3；01_Intro ML_compressed.pdf p8 |

## 4. 排名分布（全部可评测条目）

| 桶 | 条数 | id |
|---|---|---|
| 第 1 名 | 32 | q001 q002 q003 q004 q005 q006 q007 q008 q009 q011 q012 q013 q014 q015 q016 q017 q018 q020 q021 q023 q026 q027 q029 q030 q031 q032 q033 q034 q035 q036 q038 q039 |
| 第 2-5 名 | 4 | q010 q019 q022 q040 |
| 第 6-20 名 | 3 | q025 q028 q037 |
| 未召回 | 1 | q024 |

## 5. 评测集自检（口径验证）

✅ 每条可评测 query 的 `expected_keywords` 都能在期望页的片段文本里找到。

✅ no_answer 条目未在语料中反查出答案（`must_not_appear` 均未出现）。
