# 模板拆解指南（Agent 专用）

本文档描述如何把用户提供的 .docx 简历拆解为可复用的 docxtpl Jinja2 模板。
目标：拆解后模板能通过 `render_resume.py` + profile 数据渲染出新简历，
保留原始排版样式，只替换内容。

---

## 任务定位

输入：用户的原始 .docx 简历（版面、样式、内容都已在里面）
输出：
1. 替换了内容占位符的 .docx 模板文件（`templates/<name>/template.docx`）
2. 该模板的 README（`templates/<name>/README.md`）

核心原则：**样式由 Word 文档承载，内容由 profile 数据驱动，agent 只做注入，不做重排**。

---

## 五步法

### Step 1：结构识别

读取 docx，把文档划分为以下四类区域：

| 区域类型 | 特征 | 处理方式 |
|---------|-----|---------|
| 静态文本 | 不因人而异（如"教育背景"标题） | 保留原文，不注入占位符 |
| 单值变量槽 | 每人一个值（姓名、GPA、学校） | 替换为 `{{ ... }}` |
| 重复区 | 每个经历/技能条目一份 | 用 `{%p for ... %}...{%p endfor %}` 包裹 |
| 条件区 | 有些人有、有些人没有（如政治面貌） | 用 `{%p if ... %}...{%p endif %}` 包裹 |

识别顺序：先找重复区（最容易识别），再找条件区，再找单值变量，最后确认静态文本。

### Step 2：占位符注入

按以下规则替换文档内容：

**命名空间约定**：模板统一使用英文 canonical 键（`profile.basic.name`、`profile.academics.school`、`exp.fields.time_range`...）。用户 `信息.md` 里写的中文键由 parser 自动映射。完整映射表见 `references/profile-structure.md`。

**单值占位符（行内替换）**：
```
原文：张三
替换为：{{ profile.basic.name }}

原文：北京大学
替换为：{{ profile.academics.school }}

原文：3.8/4.0
替换为：{{ profile.academics.gpa | default('') }}
```

**循环块（段落级）**：

docxtpl 的段落级标签写在独立段落里，用 `{%p ... %}` 语法：

```
{%p for exp in profile.experiences %}
{{ exp.title }}    {{ exp.fields.time_range | default('') }}
{{ exp.fields.role | default('') }}
{%p for bullet in exp.bullets %}
• {{ bullet }}
{%p endfor %}
{%p endfor %}
```

**条件块（段落级）**：
```
{%p if profile.basic.political_status %}
政治面貌：{{ profile.basic.political_status }}
{%p endif %}
```

### Step 3：样式保留 + 简历排版纠偏

**默认保留**：段落样式名、字体/字号/颜色/行距、表格边框/列宽/行高、页边距页眉页脚。

**但是**：不要机械照搬原 docx 的 run 级 bold/italic/等宽空格对齐。普通用户的原 docx 经常做错这几件事，需要主动纠偏：

| 常见错误 | 纠偏默认 |
|----------|----------|
| 整段内容都加粗（包括 bullets、正文） | 只保留"项目名/角色/分类标签"加粗；bullets 用正文权重；自我评价全段不加粗 |
| 用连续空格近似右对齐时间 | 换成 `\t` 分隔 + 右对齐 tab stop（tab stop 位置按 cell/text 宽度设置，A4 单栏约 8000-8300 twips） |
| 大面积斜体 / 下划线装饰 | 去掉；加粗已足够做强调 |
| 多种强调方式混用（粗+斜+下划线+变色） | 统一只用加粗 |

"名称加粗、重点词加粗、时间右对齐、正文权重 bullets"是简历行业通用做法，不是偏好，主动套用。

**run 级处理要点**：docxtpl 渲染时占位符所在 Run 的格式会被继承。想要"项目名加粗、时间不加粗"，就把一个段落拆成三个 run：`{{ 项目名 }}｜{{ 角色 }}`（粗体 run）+ `\t`（普通 run）+ `{{ 时间 }}`（非粗体 run），并给该段落设 `<w:tabs><w:tab w:val="right" w:pos="8300"/></w:tabs>`。

### Step 3.5：去个人化（改模板前必做）

模板会进入 skill 的公共目录，**任何用户身份信息都不能留下**：

- **原 docx 不留在 skill 目录**：用户原始 docx 只能放在用户工作区的 `.resume/cache/`；构建完成后把 skill 目录里的 `source-resume.docx` 删掉。
- **构建脚本不硬编码用户字符串**：如果 find-and-replace 需要锚点，先让用户把原 docx 里的真实值替换成通用中文占位符（"张三"→"{{姓名}}"）再驱动脚本；或直接在 docx XML 层按 run 索引定位，不依赖字面值。
- **README 示例只用占位符**：用 `<姓名>`、`<手机号>`、`<邮箱>`、`<YYYY年M月D日>`、`<学校>`、`<专业>`、`<GPA（排名）>` 等通用占位符，不用真实数据。
- **扫描验证**：保存后用 `grep -rE "<用户可能出现的姓名|邮箱|电话|学号>" assets/templates/<name>/` 应返回空；含原始 docx 的模板目录 `find ... -name "source*.docx"` 也应返回空。

### Step 4：构件规避

以下 Word 构件 docxtpl 不支持或支持有限，必须在用户提供模板前检查并处理：

| 不支持的构件 | 问题 | 处理方式 |
|-----------|-----|---------|
| 文本框（Text Box） | 内容在独立 XML 节点，docxtpl 无法注入 | 把文本框内容改为普通段落 |
| SmartArt | 完全不支持 | 删除，用纯文本列表替代 |
| 图文混排（文字环绕图片） | 渲染后布局错位 | 改为嵌入式图片或删除 |
| 分栏（多列布局） | 部分版本渲染异常 | 改为单栏；或用表格模拟双栏 |
| 公式框（Equation） | 完全不支持 | 不适用于简历场景，直接删 |
| 超链接（Hyperlink） | 部分情况丢失格式 | 可保留，但渲染后需验证 |
| 目录（TOC） | 不支持自动更新 | 简历不应有目录，直接删 |
| 页眉/页脚中的变量 | 支持但需额外处理 | 简历通常不需要，保持静态文本 |

**遇到以上构件时**：先告知情况，再提出简化方案，等确认后处理。

### Step 5：产出 README

每个模板目录必须包含 README，内容见"README 必写字段"节。

---

## 占位符语法完整示例

### 普通值（行内）

```jinja2
{{ profile.basic.name }}
{{ profile.basic.phone }}
{{ profile.basic.email }}
{{ profile.basic.target_role | default('') }}
{{ profile.academics.school }}
{{ profile.academics.gpa | default('') }}
{{ profile.academics.rank | default('') }}
```

### 条件（段落级）

```jinja2
{%p if profile.basic.political_status %}
政治面貌：{{ profile.basic.political_status }}
{%p endif %}
```

### 经历循环（段落级）

```jinja2
{%p for exp in profile.experiences %}
{{ exp.title }}        {{ exp.fields.time_range | default('') }}
{{ exp.fields.role | default('') }}    {{ exp.fields.organization | default('') }}
{%p for bullet in exp.bullets %}
·  {{ bullet }}
{%p endfor %}
{%p endfor %}
```

### 技能列表（行内循环，适合技能在同一段落）

```jinja2
{% for skill in profile.skills %}{{ skill }}{% if not loop.last %}；{% endif %}{% endfor %}
```

### 奖项列表（段落级循环）

```jinja2
{%p for award in profile.awards %}
·  {{ award }}
{%p endfor %}
```

### 嵌套访问 extras

```jinja2
{%p if profile.extras['自我评价'] %}
{%p for line in profile.extras['自我评价'] %}
{{ line }}
{%p endfor %}
{%p endif %}
```

### 安全访问（防止 KeyError）

```jinja2
{{ profile.basic.get('gpa', '') }}
{{ profile.academics.get('courses', '') }}
```

---

## 构件规避清单

在开始注入占位符前，必须先扫描以下清单并处理：

```
[ ] 文档中是否有文本框 → 改为普通段落
[ ] 文档中是否有 SmartArt → 删除，改纯文本
[ ] 图片是否为文字环绕 → 改为嵌入式（inline）
[ ] 是否使用了分栏 → 评估是否影响渲染；互联网岗简历通常不分栏
[ ] 是否有超链接 → 标记，渲染后验证
[ ] 是否有合并单元格 → docxtpl 支持，但占位符不能跨合并格；检查是否跨格
[ ] 是否有条件样式（样式随内容自动变化）→ 手动检查渲染结果
```

---

## README 必写字段

每个模板的 `README.md` 必须包含以下内容（格式不限，内容不可缺）：

### 1. 适用场景

说明该模板适合哪类岗位/企业类型：

```markdown
## 适用场景
- 互联网校招：技术/产品方向
- 单栏布局，简洁量化风格
- 不带照片
```

### 2. 必需的 profile 字段

列出渲染时必须存在、否则会出现空白的字段：

模板 README 里 `## 必需 profile 字段` 小节的内容会被 `scripts/preflight.py:parse_readme_required` 读取，渲染前自动校验；缺字段会以白话提示用户，不会静默渲染出空白简历。

```markdown
## 必需 profile 字段
- basic.name
- basic.phone
- basic.email
- academics.school
- academics.major
- academics.degree
- experiences（至少 1 条）
```

### 3. 使用的 Word 样式

列出模板用到的段落样式名，方便排查格式问题：

```markdown
## Word 样式清单
- Normal（正文）
- Heading 2（section 标题）
- List Bullet（bullet 列表项）
```

### 3.5 排版策略（必写）

明确写出哪些元素加粗、哪些右对齐、bullets 权重，让后续改模板的人不用猜：

```markdown
## 排版策略
- 加粗：项目名 + 角色、分区标题、荣誉技能的分类标签（"曾获荣誉："等）
- 非加粗：自我评价全段、bullets、时间、荣誉技能分类后的内容
- 时间右对齐：项目标题行用 `\t` 分隔，段落加右对齐 tab stop at 8300 twips
- 强调唯一方式：加粗；不使用斜体 / 下划线 / 变色
```

### 4. 已知限制

说明该模板的已知问题或约束：

```markdown
## 已知限制
- 经历条目超过5条时可能超出一页，需用户手动删减
- 技能列表超过8条时右侧可能截断，建议合并同类项
- 政治面貌字段若缺失，整行隐藏（条件块）
```

---

## 注意事项

1. **不创建新文档**：从用户原始 docx 复制修改，不从零新建
2. **保留全部样式**：不删任何 Word 样式，哪怕当前没用到
3. **不改段落顺序**：占位符注入不改变原始段落位置
4. **循环块和条件块标签必须单独成段**：`{%p %}` 标签所在段落不能有其他文本内容
5. **测试渲染**：注入后用一份最小 profile 跑一次渲染，确认无 Jinja 错误
6. **渲染失败时**：优先检查 `{%p %}` 标签是否在独立段落，其次检查变量路径拼写
