# classic-zh 模板说明

## 适用场景
中文正式风简历，一页。国企/选调/考研推免首选。

## 所需字段
- profile.basic: name, gender, birthdate, phone, email
- profile.academics: school, college, major, gpa, rank, entry_date
- profile.experiences[]: title, fields{时间, 角色}, bullets[]
- profile.student_work[]: str
- profile.skills[]: str
- profile.awards[]: str

## 样式
- 姓名：宋体加粗 22pt 居中
- Section 标题：宋体加粗 12pt，带底部分割线
- 正文：宋体 10.5pt
- 所有样式的西文字体：Times New Roman
- 页边距：上下左右 1.5cm

## 已知限制
- 仅单栏布局
- 不含照片占位
- 最多 6 条经历（更多会超一页，用户可在 Word 中后调）

## 重新生成
```bash
cd assets/templates/classic-zh
python _build_template.py
```
