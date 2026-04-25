---
name: make-resume
description: Use when the user wants to build, update, or generate a Chinese resume — especially university students applying for fall recruiting, internships, project applications, 国企/选调, or similar. Triggers include "帮我写简历", "秋招简历", "简历模板", "从我的文件夹抽个人信息", "把 JD 变成简历", or dropping personal documents into a folder and mentioning job hunting.
version: 6
---

# Resume Skill

## 目标

目标用户是**大学生**。所有决策按这个顺序：

1. 能自动推断的**绝不问用户**
2. 能宽容解析的**绝不报错**
3. 能默默成功的**绝不打扰**
4. 必须说话时**只说人话** —— 不暴露 YAML / JSON / schema / Jinja / stack trace

简历生成的唯一目的：**让 HR 直观清晰地认识到「你很强，你就是这个岗位所需要的人」**。

---

## 知识库结构（Markdown-first）

个人知识库的**正文形态只有 Markdown**。JSON / YAML 只承载状态、偏好、manifest。

```
<workspace_root>/
  个人信息总览.md            # 总览页：基础信息 + 学业 + 项目索引 + 技能 + 奖项
  项目档案/
    <项目A>.md              # 单个项目的详细证据页
    <项目B>.md
    ...
  .resume/
    state.json              # 控制面：是否已初始化、何时、主档路径
    preferences.yml         # 用户偏好（模板、脱敏、单页倾向等）
    manifest.jsonl          # 文件树快照（给 diff 用，不承载知识）
```

**分工**：

- `个人信息总览.md` 是 Agent 进入仓库后的第一阅读对象，是索引层。
- `项目档案/*.md` 是证据页，Agent 按需深读，不做强结构化解析。
- `.resume/` 三个文件只管「做过没、变了没、用户偏好什么」，**不存知识**。

---

## 第一步：永远先校验工作区状态

每次 Skill 被触发，**无论用户说什么**，第一件事都是跑 `validate_workspace_state`：

```python
from pathlib import Path
from scripts.state import validate_workspace_state
from scripts.phase_router import decide_phase

root = Path.cwd()
resume_dir = root / ".resume"

ws = validate_workspace_state(root, resume_dir)
# ws["status"] ∈ {"cold_start", "incremental", "fast_generate", "recovery"}
# ws["state"], ws["overview_abs_path"], ws["diff"]

phase = decide_phase(ws["status"], user_intent=<用户这次原话>)
```

四种状态 → 四条路径：


| workspace status | 触发条件                             | 默认 phase   |
| ---------------- | -------------------------------- | ---------- |
| `cold_start`     | `initialized_at` 从未设置            | `init`     |
| `incremental`    | 已初始化，manifest 与当前文件树有 diff       | `update`   |
| `fast_generate`  | 已初始化，无 diff                      | `generate` |
| `recovery`       | 状态说初始化过但 `overview_path` 指向的文件不在 | `recovery` |


user_intent 里出现「模板 / add template / change template」→ 覆盖为 `add_template`。

**纪律**：先信状态，再信 LLM。状态告诉你「做过没、变了没」，不用 LLM 猜。

---

## Phase 0: 环境自检（每次 Skill 启动必跑，任何 phase 之前）

检查 `scripts/` 目录下关键脚本是否存在（用 Glob 或 Bash `ls`）：

- `scripts/state.py`
- `scripts/render_resume.py`
- `scripts/preflight.py`

**存在 → 继续进入对应 phase。**

**不存在 → 停止，告知用户：**

> 「渲染脚本不在当前目录（找不到 scripts/render_resume.py），无法生成 DOCX。请确认你是在 skill 根目录下运行，或告诉我直接输出 Markdown 草稿作为临时替代。」

**禁止静默降级为 Markdown 输出。必须明确告知用户后，由用户决定是否接受草稿。**

---

## Phase: init

**目标**：把用户文件夹变成 Markdown 知识库（总览 + 项目档案）。**最多打扰用户一次**。

### [GATE-0] 工作区身份信号预检——完成前禁止进入 GATE-REF

执行顺序：

1. `Glob("**/*")` 列出工作区文件，排除 `.resume/`
2. 判断是否存在**身份信号**——能让 Agent 推断出"这是谁的简历"的材料：
  - 旧简历 / CV：文件名含 `简历 / resume / cv` 的 `.docx` / `.pdf`
  - 成绩单 / 学籍 / 学生证 / 录取通知：文件名或图片含相关关键词
  - 手写卡片：任意 `.md` / `.txt` 同时包含**姓名**和**联系方式**（手机号 `1[3-9]\d{9}` 或邮箱）
  - 身份证 / 户口本 类敏感扫描件（**有则确认存在即可，正文不要写出号码**）
3. 任一命中 → **GATE-0 通过**，进入 GATE-REF
4. 全部未命中 → **不进**写盘流程，向用户输出：

> 我在 `<path>` 看到了 N 个文件，但没找到能确认你身份的材料（姓名 / 学校 / 专业 / 联系方式）。简历必须有这些，否则后面会卡在 preflight。
>
> 请补充至少其中之一：
> - 旧简历（.docx / .pdf）
> - 成绩单或学籍证明
> - 一张写着「姓名 · 学校 · 专业 · 手机 · 邮箱」的 txt/md 卡片（最快的方式）
>
> 补完直接喊我继续。

5. 用户补完后再次 `Glob` → 重跑 GATE-0

**纪律**：GATE-0 是**软门控**——用户也可以明确说"我就是要用占位身份"，那就放行，但要在总览的"敏感信息"小节标记"身份字段为占位，未来需要补"。

---

### [GATE-REF] 加载 phase 必读 reference——完成前禁止进入后续步骤

Read `references/profile-structure.md`。读完后确认「GATE-REF 通过」，否则禁止继续。

---

### 1. 全局审视

> **[GATE-1] 全量扫描——完成前禁止进入归并步骤。**

执行顺序：

1. 用 `Glob("**/*")` 列出工作区所有文件，记录文件总数 **N**（排除 `.resume/` 目录本身）
2. 按分层规则逐一读取**全部** N 个文件：
  - `.md / .txt / .csv` → Read
  - `.pdf / .jpg / .png / .webp` → Read（多模态原生）
  - `.docx / .pptx / .xlsx` → `scripts.extract_text.extract_text(p, resume_dir / "cache")`
  - 其他扩展名 → 跳过，记入 noise 列表
3. 读完后向用户输出一行核查声明：
  > 「已读取 **M / N** 个文件（跳过 K 个不支持格式）。」
4. **M < N - K 时，说明有文件未读，必须补读后再继续。**

`scripts/triage_classifier.classify_all(root)` 仅作候选提示，不裁决。

读完后在心里过 audit（不必落盘）：

```
existing_overview: <path|null>       # 已有的总览或老版 信息.md
old_resume:       [...]              # 旧简历 docx / PDF
template_docx:    [...]              # 用户自带模板
strong_evidence:  [...]              # 项目材料、成绩单、证书、答辩稿
noise:            [...]
conflicts:        [...]
```

### 2. 归并为项目

用**你自己的判断**把 strong_evidence 归并到项目——依据文件名、路径、文件内容、旧简历提到的经历。不要写归并规则引擎，这一步就是 Agent 读内容做判断。

硬规则：

1. 事实以原文件为准，不编造数字/头衔/时间
2. 时间统一 `YYYY-MM` 或 `YYYY-MM ~ YYYY-MM` / `~ 至今`
3. 矛盾信息两条都保留（进项目档案的"冲突 / 待确认"小节）
4. 敏感信息（身份证 / 住址 / 学号 / 手机号）保留在总览的"敏感信息"小节——投递时由 `sanitize_for_resume` 自动脱敏

**归并启发（默认合并，不是默认拆分）**——满足任一条时，同一个档案，不新建第二份：

- 同一公司 / 同一机构 / 同一个主办方
- 时间窗完全覆盖或显著重叠，且主题相近
- 父项目 + 子任务 / 课程论文 + 衍生竞赛：父为主，子在"4. 你具体做了什么"里展开
- 原材料出现"这是我在 X 期间做的 Y"这类明确从属关系描述

不确定是否合并时先合并、在合并档案顶部加一行"待确认：是否应拆分为两份"。归并错了代价低（两份合并很便宜），拆错了代价高（要找用户澄清并手动合并）。

### 3. 写盘

```
root/
  个人信息总览.md
  项目档案/
    <项目1>.md
    <项目2>.md
    ...
```

**总览页结构**（详见 `references/profile-structure.md`）：

```markdown
# 个人信息总览

## 1. 基本档案
## 2. 学业概览
## 3. 核心经历索引
（表格：项目 | 时间 | 角色 | 一句话产出 | 详情链接）
## 4. 学生工作与校园角色
## 5. 技能与知识结构
## 6. 奖项与荣誉
## 7. 其他补充
## 8. 敏感信息（仅个人留存）
## 9. 文件版本与来源说明
```

**项目档案页固定结构**：

```markdown
# <项目名>

## 1. 项目摘要
## 2. 时间 / 角色 / 组织
## 3. 背景与目标
## 4. 你具体做了什么
## 5. 方法 / 工具 / 协作对象
## 6. 结果与量化产出
## 7. 可直接写进简历的 bullets
## 8. 来源材料
## 9. 冲突信息 / 待确认事项
```

项目档案允许详细、允许保留冲突，不追求结构化，专供 Agent 深读。

### 3.5 深度自检（写盘前必跑）

写完 overview 和所有项目档案后，在心里过一遍**每一份档案**，必须同时满足：

- 来源材料 ≥ 1 条（在"8. 来源材料"里列明具体文件路径）
- 含"7. 可直接写进简历的 bullets"（最少 1 条，动词开头，带可量化细节）
- 含"9. 冲突信息 / 待确认事项"（没有冲突就写"无"；不要省略这一节）
- 没有出现"（具体内容见 xxx.pdf）""待补充""暂缺记录"这类占位字符——若材料里确实没信息，写"知识库未采集详细记录，若要投递需补一份工作日志"

任何一份档案不满足 → 回到第 2 步，重新深读对应来源材料再补写。**禁止**以"先凑一份、后面再补"的名义进入下一步。

### 3.6 重建保护（init 如果发现已有 overview / 项目档案）

当工作区本来就有 `个人信息总览.md` 或 `项目档案/`（例如用户在半成品状态下请求"全部重来"），在写新内容之前：

1. 把既有 `个人信息总览.md` 和 `项目档案/` 整体移动到 `.resume/backup-<场景描述>/`（场景描述举例：`backup-首次重建前`、`backup-用户请求重写前`，用中文或简单英文，不用时间戳）
2. 告诉用户"旧版已备份到 `<路径>`"
3. 再开始重建

**禁止直接覆盖**既有整理稿——用户可能已经手改过内容。

### 4. 更新 state + manifest

```python
from scripts.state import read_state, write_state
from scripts.manifest_scan import build_snapshot, commit_manifest
from datetime import datetime, timezone, timedelta

tz = timezone(timedelta(hours=8))
state = read_state(resume_dir)
state["overview_path"] = "个人信息总览.md"
state["initialized_at"] = datetime.now(tz).isoformat(timespec="seconds")
state["phase"] = "initialized"
write_state(resume_dir, state)

commit_manifest(resume_dir, build_snapshot(root))
```

### 5. 白话反馈 + 阶段完成声明

> 初始化完成。已读取 M/N 个文件，整理了 `个人信息总览.md` 和 `项目档案/` 下的 **P 个项目页**。你先看一遍，有要改的直接改；改完发我 JD 就能生成简历。

**✔ Phase: init 完成。state 已更新，manifest 已提交。**

---

## Phase: update

**目标**：文件变更同步进知识库。**只问一次**。

### [GATE-REF] 加载 phase 必读 reference——完成前禁止进入后续步骤

Read `references/profile-structure.md`。读完后确认「GATE-REF 通过」，否则禁止继续。

---

```python
diff = ws["diff"]   # 已由 validate_workspace_state 算好
```

白话问：

> 我发现你文件夹里有这些变化：
> ＋新增：xxx.pdf, yyy.png
> ～改动：zzz.docx
> －删除：aaa.jpg
> 要不要同步到知识库？[回车=是，n=否]

**同步（用户回车）**：

- 读 `diff["new"] + diff["modified"]` 的文件
- **你自己判断**每个新/改动文件影响哪些项目页或总览字段（不写归并引擎）
- 改动相关 `项目档案/*.md`；刷新 `个人信息总览.md` 的索引表、来源说明、学业数据等
- 对 `diff["deleted"]`：**不自动删**项目页，在对应页的"冲突 / 待确认"里记一句「 已删除，，内容先保留」
- `commit_manifest(resume_dir, build_snapshot(root))`
- 更新 `state["last_update_at"]`
- 白话摘要：「加了 X 项目页，更新了 GPA 和 3 个项目索引」

**不同步（用户回 n）**：

- 什么都不改
- 仍然 `commit_manifest(...)`，标记当前快照已确认忽略，下次不再打扰

---

## Phase: generate

**目标**：在已有知识库上写简历。**不回扫文件夹**，默认从总览页进、按需深读项目档案。

> **输出格式铁律：最终交付物必须是 DOCX（+可选 PDF）。**
> **禁止将 Markdown 作为最终简历输出。**
> 若渲染失败，必须明确告知用户失败原因，再询问是否需要 Markdown 草稿作为临时替代——不得静默降级。

---

### [GATE-2] 模板确认——完成前禁止生成任何简历内容

```python
from scripts.state import read_preferences, write_preferences
prefs = read_preferences(resume_dir)
```

按以下决策树执行，**每条路径都必须有明确结果后才能继续**：


| 情况                                     | 动作                                                 |
| -------------------------------------- | -------------------------------------------------- |
| `prefs["preferred_template"]` 有值且文件存在  | 使用该模板，继续                                           |
| `prefs["preferred_template"]` 有值但文件不存在 | 告知用户路径失效，重新询问                                      |
| 无偏好                                    | 询问用户：「你有想用的简历模板（.docx）吗？有的话给我路径；没有我用默认模板。」等用户回复后继续 |
| 用户明确说用默认 / 无模板                         | 使用 `assets/templates/classic-zh/template.docx`，继续  |
| 用户给了新模板路径                              | 走 [Phase: add_template]，处理完后回到 GATE-2 确认           |


**✔ GATE-2 通过：template_path 已确定 → 进入正文生成。**

---

### [GATE-3] 加载写作指南——完成前禁止生成任何简历内容

**必须在 GATE-2 通过后、进入「要 JD」步骤之前，逐一 Read 以下 5 个 reference 文件。**全部读完后确认「GATE-3 通过」，否则禁止继续。

1. `references/application-framing.md` ← 核心纲领（五大原则、四阶段、六项 review）
2. `references/resume-writing-rules.md`
3. `references/bullet-patterns.md`
4. `references/jd-to-resume-mapping.md`
5. `references/chinese-resume-conventions.md`

**纪律**：这不是"按需加载"——是硬性前置条件。跳过任何一个文件等于跳过 GATE-3，后续生成的简历质量不可接受（典型表现：骨架选错、bullet 单薄、自我评价与经历重复）。

**✔ GATE-3 通过：5 个 reference 全部已读 → 进入「要 JD」步骤。**

---

### 1. 要 JD

- 用户给了 JD → 读出 JD 文本
- 用户没给 JD → 问：「把 JD 粘过来，或给我 JD 文件路径」
- 用户明确要「通用简历 / 不针对岗位」→ 跳过 JD，写一版通用模板简历（默认骨架）

### 3. 读知识库

**顺序**：先总览，再按需深读项目档案。

```python
from scripts.parse_profile import parse_overview
overview = parse_overview(ws["overview_abs_path"])
# overview: {basic, academics, project_index[...], student_work, skills, awards, other, extras}
```

根据 JD 关键诉求 + `overview["project_index"]` 的一句话产出，**挑选要深读的项目**——不要全读。深读方式：直接 `Read` 对应 `项目档案/*.md`。

### 4. 四阶段生成

按 `references/application-framing.md`：

1. **target_model** — JD → 岗位画像
2. **evidence_slate** — 候选经历打分、选 2-4 条
3. **master_facts** — 锁硬事实（学校、时间、GPA、头衔、数字）
4. **resume_outline + 正文** — 模块顺序 → bullets_plan → 逐条 bullet 填满五要素

生成 `resume_data`（canonical dict）后先别渲染。

### 5. 六项 Review

见 `application-framing.md`「六项 Review」：人岗匹配、核心叙事一致性、经历选择正确率、bullet 完整性、事实准确率、可读性。任何一项不过 → 回阶段 1-3 修 → 重跑 review。

### 6. 脱敏 + preflight + 渲染

**输出路径命名原则（硬规则）**：面向人的归档目录与文件名用"项目名/主题"，**不加日期前缀**。日期前缀只用于两种场景：`<artifact>/versions/<safe-ts>_*.docx` 的历史快照、`changes/<YYYY-MM-DD>.md` · `traces/<YYYY-MM-DD>/` 的按天分桶审计。

```python
from scripts.field_mapping import sanitize_for_resume
target_role = target_model.get("role_type_free_text")
resume_data = {"profile": sanitize_for_resume(resume_data["profile"], target_role=target_role)}

import json, subprocess, sys
from datetime import datetime, timezone, timedelta

# slug: 用户能一眼认出来的项目/公司简称（中文 OK）。去掉文件名非法字符，长度建议 ≤ 16
# 例："马来西亚科考"、"华夏基金-定量策略"、"字节-前端暑期"
slug = <根据 JD / 项目名选一个短的、可读的中文/英文 slug>

# 目录结构：<project_slug>/ 放 docx + meta；同一项目再次生成 → 直接覆盖 docx
# 若用户显式要求保留旧版本 → 先把旧 docx 挪到 <project_slug>/versions/<safe-ts>_*.docx
out_dir = resume_dir / "resumes" / slug
out_dir.mkdir(parents=True, exist_ok=True)
out_docx = out_dir / f"{slug}_简历.docx"

cfg = {
    "template": str(template_path),
    "data": resume_data,
    "out_docx": str(out_docx),
    "make_pdf": True,
    "preflight": True,
}
proc = subprocess.run(
    [sys.executable, "scripts/render_resume.py"],
    input=json.dumps(cfg), text=True, capture_output=True, check=True,
)
result = json.loads(proc.stdout)
```

`result["preflight_problems"]` 非空 → **不输出**，白话逐条报给用户，回阶段 3 修 master_facts 或阶段 2 重选经历。

### 7. 写 metadata + 报告

```python
# meta 与 docx 同目录，不再单独建日期子目录
(out_dir / "meta.json").write_text(json.dumps({
    "target_role": target_role,
    "jd_excerpt": jd_text[:200],
    "template": str(template_path),
    "skeleton": target_model["skeleton"],
    "chosen_experiences": [e["id"] for e in evidence_slate if e["decision"] == "正文"],
    "docx": result["docx"],
    "pdf": result["pdf"],
    "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
}, ensure_ascii=False, indent=2), encoding="utf-8")

state["resume_count"] += 1
write_state(resume_dir, state)
```

**发现既有时间命名的旧目录**（例如 `resumes/2026-04-20/`）：提出改名建议，不要默认延续错误。用户同意后把目录重命名为项目 slug，文件 stem 同步去掉日期前缀。

白话报告：

- 有 PDF：「简历生成好了：`<docx 路径>` 和 `<pdf 路径>`。这次突出了 `<3 条 key_proposition>`。」
- 没 PDF：「简历生成好了：`<docx>`。PDF 转换工具 LibreOffice 没装，只出 docx；要 PDF 的话装一下再叫我。」

---

## Phase: add_template

**目标**：记住用户自带模板。**不做** Jinja 改造（那是 `references/TEMPLATE_GUIDE.md` 的高级路径）。

### [GATE-REF] 加载 phase 必读 reference——完成前禁止进入后续步骤

Read `references/TEMPLATE_GUIDE.md`。读完后确认「GATE-REF 通过」，否则禁止继续。

---

1. ~~读 `references/TEMPLATE_GUIDE.md`~~（已在 GATE-REF 完成）
2. 问路径（如果用户还没给）
3. 校验：存在 & 后缀是 `.docx` / `.dotx`
4. 若模板**可直接渲染**（含 Jinja 占位符或者是 canonical 键）→ 写偏好：
  ```python
   prefs["preferred_template"] = str(Path(path).resolve())
   prefs["template_asked"] = True
   write_preferences(resume_dir, prefs)
  ```
5. 若模板是**纯 docx 没占位符** → 按 `TEMPLATE_GUIDE.md` 五步法拆成可复用模板，占位符只用英文 canonical 键（`profile.basic.name`、`profile.academics.school` …），同目录写 `README.md` 列必需字段（`scripts/preflight.py` 会读）
6. 告知：记住了，以后默认用这个模板

**去个人化纪律（硬规则）**——模板一旦进入 skill 目录就是"公共资产"，不得含任何用户身份信息：

- 模板目录禁止保留原始用户 docx（原姓名、电话、邮箱、GPA、项目名都在里面）。用完就删；用户的原始文件只放在用户工作区 `.resume/cache/` 下。
- 构建脚本禁止硬编码用户字符串（姓名、电话、邮箱、学号 …）作为查找-替换锚点——这类字符串会被 grep 扫到。如果必须用锚点：用通用中文占位符先替换一次（"张三"→"{{姓名}}"），再驱动脚本；或干脆直接在 docx XML 层定位 run 索引，不依赖用户字面值。
- README 示例只用 `<姓名>`、`<手机号>`、`<邮箱>`、`<YYYY年M月D日>` 这类通用占位符，不得用真实数据。
- 保存后扫一次：`grep -rE "<真实姓名>|<电话号>|<真实邮箱>|<学号>" assets/templates/<name>/` 应返回空。

模板处理完**不等于可以跳过 JD**——回到 generate 的第 2 步要 JD。

---

## Phase: recovery

**目标**：state 说初始化过但 `overview_path` 找不到了——**不要退回 cold_start**，evidence 可能还在。

### [GATE-REF] 加载 phase 必读 reference——完成前禁止进入后续步骤

Read `references/profile-structure.md`。读完后确认「GATE-REF 通过」，否则禁止继续。

---

1. 白话：「我记得我们之前初始化过（`<initialized_at>`），但 `<overview_path>` 找不到了。我重扫一下材料帮你把主档再整一份——旧 state 我不动。」
2. 走 init 的全局审视逻辑，但**不清空** state
3. 若原路径 stem 仍存在（比如用户把 `.md` 改名成 `.md.bak`）→ 提示用户确认后恢复
4. 否则按 init 的归并逻辑重建 `个人信息总览.md` + `项目档案/*.md`
5. 更新 `overview_path`、跑 manifest 闭环、记 `state["last_init_at"]`

---

## 错误处理

**不可谈判**：

- 不给用户看 stack trace / Python 异常
- 不让用户看到 YAML / JSON / schema / Jinja / undefined / module 这些词
- 白话三件事：**发生了什么 · 哪个文件 · 下一步怎么办**


| 场景             | 说法                                                          |
| -------------- | ----------------------------------------------------------- |
| 文件夹空           | 「我在 `<path>` 里没找到任何可用材料，先把简历素材（成绩单、获奖、项目截图、旧简历……）丢进来再叫我」    |
| 总览页解析失败        | 「你这份 `个人信息总览.md` 我没完全读懂（第 `<N>` 行附近格式有问题），我直接帮你重新整理一份」      |
| 模板路径不存在        | 「我找不到 `<path>`，路径抄错了？再发一次」                                  |
| 模板渲染失败         | 「这份模板里有个地方我没认出来，先用默认模板给你出一份」                                |
| preflight 缺字段  | 逐条白话报：「缺少「手机号」—— 请在 `个人信息总览.md` 里补上再生成」                     |
| LibreOffice 没装 | 「PDF 转换工具 LibreOffice 没装，只给你出 docx 了」                       |
| 依赖缺失           | 「缺个 Python 包，在终端跑：`pip install docxtpl pyyaml mistune ...`」 |


---

## Reference 必读清单（由 GATE-REF / GATE-3 强制执行）

每个 phase 进入实质步骤前，**必须先 Read 下表列出的全部 reference 文件**。这不是"按需加载"——是硬性前置条件，由各 phase 的 `[GATE-REF]` 或 `[GATE-3]` 门控执行。跳过 = 违反门控 = 后续产出质量不可接受。


| phase          | 必读（全部 Read 后才能继续）                                                                                                                                    |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `init`         | `references/profile-structure.md`                                                                                                                    |
| `update`       | `references/profile-structure.md`                                                                                                                    |
| `add_template` | `references/TEMPLATE_GUIDE.md`                                                                                                                       |
| `generate`     | `references/application-framing.md` · `resume-writing-rules.md` · `bullet-patterns.md` · `jd-to-resume-mapping.md` · `chinese-resume-conventions.md` |
| `recovery`     | `references/profile-structure.md`                                                                                                                    |


---

## 脚本一览


| 脚本                     | 关键入口                                                                                                                                      | 用途                                                      |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `state.py`             | `read_state` · `write_state` · `read_preferences` · `write_preferences` · `read_manifest` · `write_manifest` · `validate_workspace_state` | 读写 `.resume/` 下持久化状态；状态有效性校验（四态）                        |
| `phase_router.py`      | `decide_phase(workspace_status, user_intent)`                                                                                             | 返回 `init`/`update`/`generate`/`add_template`/`recovery` |
| `manifest_scan.py`     | `scan_and_diff` · `build_snapshot` · `commit_manifest`                                                                                    | 扫 + diff + 回写                                           |
| `triage_classifier.py` | `classify_all(root)`                                                                                                                      | **仅作 hint**：按文件名给 profile/template/evidence 候选          |
| `extract_text.py`      | `is_supported` · `extract_text(path, cache_dir)`                                                                                          | 只处理 .docx/.pptx/.xlsx；PDF/图片由 Agent 原生 Read             |
| `parse_profile.py`     | `parse_overview(path)`                                                                                                                    | 宽容解析 `个人信息总览.md` → canonical 英文键 dict（含 project_index）  |
| `field_mapping.py`     | `normalize_profile` · `sanitize_for_resume`                                                                                               | 中文 key → 英文 canonical；投递前默认脱敏                           |
| `preflight.py`         | `preflight_validate` · `parse_readme_required`                                                                                            | 渲染前关键字段校验                                               |
| `render_resume.py`     | `render` · `to_pdf` · `render_from_stdin`                                                                                                 | docxtpl 渲染（preflight + 报告式 Undefined）+ 可选 PDF           |


---

## 开发说明

- triage 只是 hint，LLM 才是 init 路由的裁决者
- canonical key 映射的单一真相是 `scripts/field_mapping.py`
- **永远不要**在 `render_resume.py` 里把 Undefined 改回静默吞掉
- **永远不要**跳过 `commit_manifest`——那会让 diff 基于陈旧快照
- **永远不要**给项目归并引入新的持久化结构层（`project_index.yml`、`facts.json` 之类）——Agent 读 Markdown 做判断就够了

