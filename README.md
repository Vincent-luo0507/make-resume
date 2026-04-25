# make-resume

为大学生设计的中文简历 Skill。**扔素材进文件夹 → 给 JD → 出 docx 简历**。

跑在 [Claude Code](https://docs.claude.com/en/docs/claude-code) 之上，依赖 Claude 模型本身的判断力做素材归并、JD 对齐、bullet 写作。

---

## 它做什么

1. **素材整理**：扫描你的工作区（旧简历 / 成绩单 / 项目 PDF / 答辩稿 / 截图 / 证书），归并出一份 `个人信息总览.md` 和若干 `项目档案/<项目>.md`。
2. **JD 对齐**：拿到岗位 JD 后，按四阶段（target_model → evidence_slate → master_facts → resume_outline）选经历、写 bullets。
3. **渲染输出**：通过 docxtpl 套用模板，输出 `.docx`（可选 `.pdf`，需本地有 LibreOffice）。

附带两套中文模板：

- `classic-zh`：单栏、宋体正式风，适合国企 / 选调 / 推免。
- `tabular-zh`：表格式、信息密度高，适合科研项目 / 学术申请。

---

## 安装

通过 [skills.sh](https://skills.sh) 一键装：

```bash
npx skills add Vincent-luo0507/make-resume
```

或者直接 git clone 到 Claude Code skills 目录：

```bash
git clone https://github.com/Vincent-luo0507/make-resume.git ~/.claude/skills/make-resume
```

然后装 Python 依赖：

```bash
pip install -r ~/.claude/skills/make-resume/requirements.txt
```

可选：装 LibreOffice 用于 docx → pdf

```bash
# Windows: choco install libreoffice-fresh
# macOS:   brew install --cask libreoffice
# Linux:   apt install libreoffice
```

要求：

- Python ≥ 3.10
- Claude Code CLI

---

## 用法

进入**用户工作区**（不是 skill 目录！），里面放你的简历素材，然后在 Claude Code 中：

```
帮我写简历
```

Claude 会自动判断当前工作区是冷启动 / 增量 / 直接生成中的哪一种状态，按 `SKILL.md` 描述的流程执行。

详见 `SKILL.md`。

---

## 工作区 ≠ Skill 目录（重要）

> **绝对不要把简历素材丢进 `~/.claude/skills/make-resume/` 或本仓库目录**

这个 skill 把用户素材整理成 Markdown 知识库，写在你 `cwd` 下：

- `个人信息总览.md`
- `项目档案/`
- `.resume/`（state、preferences、manifest、生成的 docx）

所有这些都包含 PII。Skill 仓库本身不应有任何用户数据。建议为每位求职者建一个独立的工作区目录，例如 `~/resume-workspace/`，在那里运行 Claude Code。

---

## 目录结构

```
make-resume/
├── SKILL.md                    # Claude 进入后读这个
├── README.md                   # 本文件
├── requirements.txt            # Python 依赖
├── scripts/                    # state / manifest / parse / render
├── references/                 # 分阶段加载的写作指南
└── assets/templates/
    ├── classic-zh/             # 默认模板（正式中文风）
    └── tabular-zh/             # 表格模板（科研项目向）
```

---

## 隐私 / 安全

- **不上行任何用户数据**：除 Claude API 之外不发任何网络请求；本地处理。
- **不接受外来素材**：开源仓库本身不收 PR，也不期望你处理别人的文件。这个 skill 假设你处理的是你自己（或你直接帮助的当事人）的资料。
- **docx 元数据已清洗**：仓库内所有 `.docx` 模板都已清空 `creator` / `lastModifiedBy` / `Author` 等字段，但**你自己生成的简历 docx 会带上你本机系统设置的作者信息**——介意的话生成后用 Word "文档检查器" 移除。
- **Office / PDF 解析风险**：`scripts/extract_text.py` 用 `python-docx` / `openpyxl` / `python-pptx` 解析 office 文件，这些库历史上有 zip-bomb / XXE 类问题。本 skill 默认你处理的是自己手里的可信素材；不要拿它扫陌生人的附件。
- **多模态 prompt injection**：Claude 直接 Read PDF / 图片，理论上恶意 PDF 可能注入指令。同上，自用场景不在此范围。

---

## License

MIT。详见 `LICENSE`。
