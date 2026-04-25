# tabular-zh 模板说明

## 适用场景

- 高校本科生「科研训练 / 海外科考 / 学术项目」等申请场景
- 一页、表格式、正式中文简历骨架
- 不带照片；信息密度高，不依赖花哨排版
- 六大板块固定：个人信息 · 自我评价 · 实践经历 · 组织与沟通经历 · 荣誉技能

## 必需 profile 字段

- profile.basic.name
- profile.basic.birth_display（出生日期字符串，如 "YYYY年M月D日"）
- profile.basic.phone
- profile.basic.email
- profile.academics.gpa_display（已合并 GPA 与排名展示字符串，如 "X.XX（1/N）"）
- profile.academics.major
- profile.extras.self_eval（自我评价段落列表，元素为完整段落字符串）
- profile.experiences（至少 1 条；每条含 title / fields.role / fields.time_range / bullets）
- profile.org_experiences（可空；结构同 experiences）
- profile.extras.honors_line（一行字符串；为空则整行隐藏）
- profile.extras.language_line（语言能力一行）
- profile.extras.research_line（研究与数据能力一行）
- profile.extras.comm_line（表达与记录能力一行）

## 数据形状示例

```python
profile = {
    "basic": {
        "name": "<姓名>",
        "birth_display": "<YYYY年M月D日>",
        "phone": "<手机号>",
        "email": "<邮箱>",
    },
    "academics": {
        "gpa_display": "<GPA（排名）>",
        "major": "<专业>",
    },
    "extras": {
        "self_eval": [
            "<自我评价第一段>",
            "<自我评价第二段>",
        ],
        "honors_line": "<荣誉一行简述>",
        "language_line": "<语言能力一行简述>",
        "research_line": "<研究与数据能力一行简述>",
        "comm_line": "<表达与记录能力一行简述>",
    },
    "experiences": [
        {
            "title": "<项目/论文标题>",
            "fields": {"role": "<角色>", "time_range": "<时间>"},
            "bullets": ["<要点 1>", "<要点 2>"],
        },
    ],
    "org_experiences": [
        {
            "title": "<组织/沟通类经历标题>",
            "fields": {"role": "<角色>", "time_range": "<时间>"},
            "bullets": ["<要点 1>"],
        },
    ],
}
```

模板把 `fields.role` 和 `fields.time_range` 放在项目标题同一行的左右端，标题与角色之间用全角竖线 `｜` 连接，时间靠右；模板本身不做等宽处理，靠制表空格近似对齐。

## Word 样式

- 整体单表布局，5 列 12 行
- 表头 "简历" 居中加粗
- 分区标题（自我评价 / 实践经历 / 组织与沟通经历 / 荣誉技能）横跨整行
- 中文：宋体；西文 / 数字：Times New Roman
- 页边距沿用原始 docx，保持 A4 一页

## 已知限制

- 经历 bullets 过多或分区经历超过 3~4 条会超出一页。默认建议：实践经历 ≤ 3 条，组织经历 ≤ 2 条。
- 表格合并结构是硬约束；新增分区需要直接在 `template.docx` 里改。
- 不含照片位。

## 维护说明

本模板已是最终产物，不依赖额外构建脚本。如需大改结构，直接在 `template.docx` 里编辑。
