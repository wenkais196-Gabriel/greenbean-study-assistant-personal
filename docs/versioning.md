# 版本管理方案

> 建立：**2026-09-14**。目标：让"代码、版本号、发布记录、用户数据"四者不漂移 —— 即**平滑**。
>
> **现状全部是实测**（见 §0），不是推测；建议按"成本 / 收益"排序，标 ⭐ 的是立刻能做的。

## 0. 现状（2026-09-14 核查）

| 项 | 现状 | 问题 |
|---|---|---|
| **git tag** | **0 个** | 110 个提交、42 个属于本 fork，**却没有任何版本锚点** |
| 分支 | `main` + `test/tdd-quality-audit`（**已并入 main**） | 已合并的分支还在，看起来像"有活没合" |
| 版本号 | `package.json` / `src-tauri/tauri.conf.json` / `src-tauri/Cargo.toml` 都是 `0.1.0` | 三处一致但**从未 bump**，与代码状态无关 |
| **CHANGELOG** | **无** | 变更只能靠 `git log` 读 |
| CI 触发 | `push` / `pull_request` 到 `main` + `workflow_dispatch` | **tag push 不触发**，发布与门禁没绑定 |
| **数据库迁移** | `app/db/migrations/` 是**空包**；无 `schema_version`、无 `PRAGMA user_version` | **无法判断"这个库是哪个版本建的"** |
| 上游 baseline | **从未 fetch upstream**（`refs/remotes/upstream` 为空）；fork 点靠 `planning/01` 的文字记录 | baseline 没有落到 git 里，归属叙事缺硬证据 |
| planning | 私有 git 仓库，**未配 remote** | 单点故障（`STATUS` §六 已登记） |

> fork 点实测：`5e79877 refactor: 调整python测试目录 (#89)`（上游 HEAD），
> 之后本 fork 有 **42 个提交**（`f0c5f28` → 当前）。

## 1. 分支模型：trunk-based（单人项目不要 git-flow）

| 规则 | 说明 |
|---|---|
| `main` 是唯一长期分支，**始终可发布** | 已有 CI 四 job + eval 门禁守住这条线 |
| 短命分支 `feat/… / fix/… / docs/…`，寿命 < 3 天 | 完成后 squash 合并回 `main` |
| 不引入 `develop` / `release` / `hotfix` | git-flow 的收益来自多人并行发布；单人项目只得到开销 |
| ⭐ **删掉已合并的 `test/tdd-quality-audit`** | 它是"看起来还没合"的噪音（`git branch --merged main` 已确认它在列表里） |

## 2. 版本号：semver + **与里程碑一一对齐**（这是关键）

本项目的版本号不服务"外部用户"，服务**叙事与回溯**：每个版本应对应一个可讲的状态。

| 版本 | 对应里程碑 | 判据（可验证） |
|---|---|---|
| **v0.1.0** | **工程 MVP（已完成）** | 主链路 + 界面接真实数据 + 评测双基线可复现 + 成本账本 —— 见 `README` 实测基线 |
| v0.2.0 | **R1**（基础追平 + 1 个差异化） | `planning/15` §3 的 8 项完成 + demo 录屏 |
| v0.3.0 | R2（差异化产品化 + 长尾 parity） | 期末由真实用户反馈定 |
| v1.0.0 | 真有外部用户在用 | 有人依赖它，升级路径稳定 |

**规则**：
1. **一个版本 = 一个 tag = 一个 GitHub Release**；
2. Release notes **引用当时的报告**（例：v0.2.0 引用 `eval-report-*.md` 与 `cost-and-latency.md`）——
   这比"改了哪些文件"有说服力；
3. **禁止"做了功能但不打 tag"**：代码与版本号一旦漂移，后面所有"当时的指标"都失去锚点。
4. ⭐ **现在就该打 `v0.1.0`**：42 个提交、双基线、成本账都在，这是最干净的存档点。

## 3. CHANGELOG：Conventional Commits → 可读的变更史

- **已完成的一半**：本 fork 的提交信息已经是 `feat(scope): …` / `fix(scope): …` / `docs: …` 约定
  （42 个提交里 `feat` 31 / `docs` 7 / `fix` 5 / `chore` 5 / `refactor` 3 …）——**这是能自动生成 CHANGELOG 的前提**；
- **要补的一半**：`CHANGELOG.md`（Keep a Changelog 格式，已随本批产出）：
  - `Unreleased` 段**随手记**（合并 PR 时补一行即可）；
  - 打 tag 时把 `Unreleased` 落成版本段，写上日期；
- **上游历史不重写**：v0.1.0 只写**本 fork** 的变更（`5e79877` 之后的 42 个提交），
  上游历史用一行说明归属，避免把别人的 commit 记成自己的（`05` 号文档的叙事红线）。

## 4. CI 作为版本门禁

| 现状 | 建议 |
|---|---|
| 只在 push/PR 到 `main` 时跑四 job | ⭐ **加 tag 触发**：`on.push.tags: ["v*"]` —— tag 与门禁绑定，"发布即验证" |
| 无 Release 流程 | tag push 后**手动**创建 Release（Release notes 用 CHANGELOG 的对应段） |
| — | **不做**产物打包/自动发布：本项目是源码分发，打包留到阶段 4 |

## 5. ⭐ 数据迁移策略（本地应用最容易被忽略、代价最高的一块）

**为什么这条最重要**：本项目的"版本"不只是代码 —— 用户机器上还有 **SQLite 库、上传文件、明文 `api_key`**。
**代码升级了但库没迁移 = 用户数据坏掉**，这才是本地应用"平滑升级"的真正难点。

**已经做对的（但零散、只写在 AGENTS / specs 里）**：

| 实践 | 位置 |
|---|---|
| 新表一律 `CREATE TABLE IF NOT EXISTS`（纯新增可自动补） | `app/db/init_db.py` |
| 旧库启动**幂等补列**（`analysis_results.summary`） | 同上（`us-stage2-tools-wiring` §5） |
| 换 embedding 模型时**明确报错**（vec0 维度不能原地改） | `init_db` |
| 生产库与上传文件**不进版本控制**（含明文 key） | `.gitignore` |

**缺的**：

1. **没有版本锚** → 无法判断"这个库是哪个版本建的"，也就无法给出"升级要做什么"；
2. **`app/db/migrations/` 是空包** → 有位置、没内容、没调用点；
3. **升级路径没有成文**（"换模型必须删库重建索引"只写在 AGENTS 的注意事项里）。

**建议（分三步，每步成本都低）**：

| 步骤 | 做法 | 成本 |
|---|---|---|
| 1. 加版本锚 | 用 SQLite 内置 `PRAGMA user_version`（零新表）或 `schema_meta` 表记录 `schema_version` | 0.5 天 |
| 2. 启动时检查 | `init_db` 读 `user_version`：**低于当前** → 顺序执行迁移函数（每个函数幂等）；**高于当前**（用旧代码开新库）→ **明确拒绝启动**，避免写坏 | 0.5 天 |
| 3. 写清升级路径 | 新增 `docs/upgrade.md`：跨版本升级要做什么（例："v0.1 → v0.2 无需操作；换 embedding 模型必须删库重建索引"） | 0.5 天 |

> **验收标准**：能回答"从 v0.1.0 升到 v0.2.0，我机器上的库会发生什么"。
> **停止条件**：能回答这个问题即停 —— 不引入 Alembic 之类的重型迁移框架（单人项目不值）。

## 6. 与上游 fork 的关系（本仓库特有的版本问题）

- **已定**（`AGENTS.md`）：不向上游提交 PR、不同步上游，一切只在 `origin` 推进；
- **要补**：把 **baseline 锚点落进 git**，别只写在 planning 的文字里：
  - `docs/upstream-baseline.md` 记录：上游仓库 + fork 点 `5e79877` + 本 fork 起点 `f0c5f28`
    + 我在上游的原始贡献（PR #26，48 files / +5466 行）；
  - 可选：`git remote add upstream … && git fetch upstream` 一次，让 `merge-base` 能算出 fork 点（**只 fetch，不同步**）；
- **理由**：将来若有人问"这段是你写的吗"，能一条命令给出答案；这也是 `05` 号求职叙事的证据链。

## 7. 展示面（GitHub 上的"版本"是给谁看的）

| 动作 | 为什么 |
|---|---|
| Release notes 写好 | 面试官/用户看到的"进展时间线"，比 README 更有说服力 |
| 用 **Issues** 记 R1/R2 里程碑讨论 | `13` 号对标结论：RAGFlow 等用 issue 跟踪 roadmap。让规划**在 GitHub 上可见**，而不是只活在私有 planning 里 |
| README 顶部 badge（CI 状态） | 低成本专业感；`eval-gate` job 的存在本身就是差异化 |
| `docs/roadmap.md`（公开，本批产出） | 补上"公开侧没有路线图"的缺口 |

## 8. 立刻可做的动作（按性价比排序）

| 动作 | 成本 | 收益 | 谁做 |
|---|---|---|---|
| ⭐ 删掉已合并的 `test/tdd-quality-audit` | 1 分钟 | 分支列表不再误导 | 我（可立刻做） |
| ⭐ 打 `v0.1.0` tag + Release | 5 分钟 | 从"0 个版本锚点"到"有历史"；Release 可写实测指标 | **需你确认版本号语义** |
| ⭐ CI 加 tag 触发 | 10 分钟 | 发布与门禁绑定 | 我 |
| CHANGELOG（本批已产出） | ✅ | 变更可追溯 | 已完成 |
| `docs/roadmap.md`（本批已产出） | ✅ | 公开侧有路线图 | 已完成 |
| `PRAGMA user_version` + 启动检查 + `docs/upgrade.md` | 1.5 天 | 升级不再靠运气 | 进 R1（见 `planning/15` 建议） |
| planning 推私有 remote | 10 分钟 | 消除单点故障 | **需你给仓库地址** |
| `docs/upstream-baseline.md` | 20 分钟 | 归属证据链 | 我 |
