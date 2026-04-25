# Profile 结构规范（Markdown-first 知识库契约）

知识库采用**总览 + 项目档案**两层结构。`scripts/parse_profile.py` 只解析总览页的索引层；项目档案交给 Agent 按需深读。

```
<workspace_root>/
  个人信息总览.md        # 唯一总览，Agent 入口
  项目档案/
    <项目A>.md          # 单个项目的详细证据页
    <项目B>.md
    ...
```

**分工**：

- 总览页：基础档案 + 学业 + 项目索引 + 技能/奖项/其他 —— 所有高稳定性、结构化字段落在这里
- 项目档案页：单个项目的背景、动作、方法、结果、来源、冲突 —— 允许详尽，允许保留矛盾

解析器原则：**输入宽，输出窄**。

- 宽：表格 OR `- 字段：值` 列表 OR 两者混用
- 宽：section 标题有同义词表
- 宽：未知 section 进 `extras`
- 窄：输出 canonical dict 给模板用

---

## 总览页（个人信息总览.md）

### 固定结构

```markdown
# 个人信息总览

## 1. 基本档案
（姓名 / 手机 / 邮箱 / 学校 / 专业 / 学历 / 年级 / 政治面貌 / 意向岗位 等）

## 2. 学业概览
（GPA / 排名 / 核心课程 / 语言成绩 / 证书）

## 3. 核心经历索引
| 项目 | 时间 | 角色 | 一句话产出 | 详情 |
|---|---|---|---|---|
| 华夏基金训练营 | 2025-07 | 产品策略负责人 | 大学生投资者画像 | [项目档案/华夏基金.md](项目档案/华夏基金.md) |

## 4. 学生工作与校园角色

## 5. 技能与知识结构

## 6. 奖项与荣誉

## 7. 其他补充

## 8. 敏感信息（仅个人留存，按需保留）
（身份证 / 住址 / 学号 —— 默认由 sanitize_for_resume 脱敏，不进简历）

## 9. 文件版本与来源说明
```

### Section → canonical key 映射


| Canonical key   | 接受的标题关键词                                  | 内部类型                      |
| --------------- | ----------------------------------------- | ------------------------- |
| `basic`         | 基本档案、基本信息、个人档案、基础资料                       | dict                      |
| `academics`     | 学业概览、教育背景、学习经历、学历                         | dict                      |
| `project_index` | 核心经历索引、项目索引、经历索引                          | list[dict]                |
| `experiences`   | 核心经历、项目经历、实习经历（deep-list 兼容路径，带 `### 条目`） | list[experience]          |
| `student_work`  | 学生工作、校园角色、校园经历、学生干部                       | list[string 或 experience] |
| `skills`        | 技能与知识结构、技能、能力                             | list[string]              |
| `awards`        | 奖项与荣誉、奖项、荣誉、获奖、荣誉奖项                       | list[string]              |
| `other`         | 其他补充、其他、证书、语言、兴趣                          | list[string]              |
| `sensitive`     | 敏感信息、仅个人留存                                | dict                      |
| `sources`       | 文件版本与来源说明、来源、版本说明                         | list[string]              |


标题匹配方式：去掉前缀数字空格后，大小写不敏感子串匹配。不匹配的 `##` 标题进 `extras[标题名]`，不丢。

### `basic` / `academics` 两种写法

表格形式（推荐）：

```markdown
| 字段 | 值 |
|-----|---|
| 姓名 | 张三 |
| 学校 | 示例大学 |
```

列表形式也支持：

```markdown
- 姓名：张三
- 学校：示例大学
```

冒号可中文「：」或英文「:」。字段名中文 → 英文 canonical（`姓名→name`、`学校→school` 等）见 `scripts/field_mapping.py`；未映射的中文 key 原样保留。

### `project_index` 表格

核心经历索引表是**新架构的心脏**。列名识别支持：


| 认得的表头                      | canonical 列名                         |
| -------------------------- | ------------------------------------ |
| 项目 / 经历 / 名称 / name        | `name`                               |
| 时间 / 起止 / time             | `time_range`                         |
| 角色 / 职位 / 岗位 / role        | `role`                               |
| 一句话产出 / 一句话 / 产出 / summary | `one_liner`                          |
| 详情 / 档案 / link / detail    | `detail_path` （自动提取 markdown 链接 URL） |


列顺序不敏感，最少有 `项目` 一列即可，其余缺失就留空。

### `sensitive` 小节

`身份证号 / 住址 / 学号 / 籍贯 / 手机号完整` 等只留仓库、不投简历的字段放这里。`sanitize_for_resume` 默认脱敏；`target_role` 是选调/公务员时允许保留籍贯。

---

## 项目档案页（项目档案/<项目名>.md）

### 固定结构

```markdown
# <项目名>

## 1. 项目摘要
一句话说清这是什么项目，最值得写进简历的价值是什么

## 2. 时间 / 角色 / 组织
- 时间：
- 角色：
- 组织/项目归属：

## 3. 背景与目标

## 4. 你具体做了什么
（强调个人动作，不写空泛项目介绍）

## 5. 方法 / 工具 / 协作对象

## 6. 结果与量化产出

## 7. 可直接写进简历的 bullets
（2-5 条沉淀候选，generate 时 Agent 从这里挑）

## 8. 来源材料
（列出该项目主要来自哪些文件）

## 9. 冲突信息 / 待确认事项
（不同材料之间时间、角色、数字不一致的，不要偷偷统一）
```

### 硬规则

1. 事实以原文件为准，**不编造数字/头衔/时间**
2. 时间统一 `YYYY-MM` 或 `YYYY-MM ~ YYYY-MM` / `~ 至今`
3. 矛盾保留在「9. 冲突信息」，让用户选
4. 每个项目对应总览「核心经历索引」的一行；索引与档案页双向对齐
5. **项目档案页不归 parser 管**——Agent 生成简历时 Read 它做判断

---

## 模板层字段访问路径

渲染模板（docxtpl Jinja2）访问 canonical profile：


| 内容           | 访问路径                                                         |
| ------------ | ------------------------------------------------------------ |
| 姓名           | `profile.basic.name`                                         |
| 手机           | `profile.basic.phone`                                        |
| 邮箱           | `profile.basic.email`                                        |
| 意向岗位         | `profile.basic.target_role`                                  |
| 学校           | `profile.academics.school`                                   |
| 专业           | `profile.academics.major`                                    |
| GPA          | `profile.academics.gpa`                                      |
| 经历循环         | `profile.experiences`（list；由 Agent 在 generate 时从项目档案合成后塞给模板） |
| 单条经历标题       | `exp.title`                                                  |
| 单条经历时间       | `exp.fields.time_range`                                      |
| 单条经历角色       | `exp.fields.role`                                            |
| 单条经历 bullets | `exp.bullets`                                                |
| 技能列表         | `profile.skills`                                             |
| 奖项列表         | `profile.awards`                                             |
| 其他 section   | `profile.extras["<中文标题>"]`                                   |


**关键**：`profile.experiences` 给模板用的是**generate 阶段 Agent 合成后的结构**，不是 parser 从总览页抽的。总览页只给 `project_index` 这层索引；bullets 从项目档案深读后由 Agent 写进 resume_data。

---

## 给 LLM 的硬规则（init / recovery 时从 evidence 综合知识库）

1. 事实一律以原文件为准，**不编造数字、头衔、时间**
2. 时间写 `YYYY-MM` 或 `YYYY-MM ~ YYYY-MM`；在读用 `YYYY-MM ~ 至今`
3. 缺字段就留空或整条省略，**不要为了格式完整而造假**
4. 矛盾两条都保留——总览页不解决冲突，项目档案页保留冲突
5. 敏感信息（身份证 / 住址 / 学号 / 手机号完整）写到总览「8. 敏感信息」，默认脱敏不进简历
6. 项目归并靠判断，不靠规则引擎：看文件名、路径、内容、旧简历提到的经历，能合就合，有疑义就保留

