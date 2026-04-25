"""Canonical field names for resume data (bilingual keys).

Users write 信息.md in Chinese. Internally the skill uses English canonical
keys (profile.basic.name, profile.academics.school, ...) so templates and
preflight checks have a single stable contract.

This module is the single source of truth for the Chinese→English mapping.
"""

from typing import Any

# Chinese → English canonical key mappings.
# When a user writes `| 姓名 | 张三 |` in 信息.md we normalize to `name: 张三`.
# Unknown Chinese keys are passed through so no data is lost; templates can
# still reach them via the original Chinese key.

BASIC_KEY_MAP: dict[str, str] = {
    "姓名": "name",
    "名字": "name",
    "性别": "gender",
    "年龄": "age",
    "出生年月": "birth",
    "生日": "birth",
    "手机": "phone",
    "电话": "phone",
    "手机号": "phone",
    "联系方式": "phone",
    "邮箱": "email",
    "email": "email",
    "e-mail": "email",
    "微信": "wechat",
    "学校": "school",
    "院校": "school",
    "在读/毕业院校": "school",
    "在读院校": "school",
    "毕业院校": "school",
    "专业": "major",
    "学历": "degree",
    "学位": "degree",
    "年级": "grade",
    "毕业年份": "graduation_year",
    "政治面貌": "political_status",
    "所在地": "location",
    "籍贯": "hometown",
    "意向岗位": "target_role",
    "目标岗位": "target_role",
    "求职意向": "target_role",
    "身份证号": "id_number",
    "住址": "address",
    "家庭住址": "address",
    "学号": "student_id",
}

ACADEMICS_KEY_MAP: dict[str, str] = {
    "学校": "school",
    "院校": "school",
    "专业": "major",
    "学历": "degree",
    "学位": "degree",
    "时间": "time_range",
    "起止": "time_range",
    "入学时间": "start_date",
    "毕业时间": "end_date",
    "gpa": "gpa",
    "绩点": "gpa",
    "排名": "rank",
    "专业排名": "rank",
    "相关课程": "courses",
    "核心课程": "courses",
    "荣誉": "honors",
    "主要荣誉": "honors",
    "学业成绩": "honors",
    "学术成果": "academic_output",
}

EXPERIENCE_FIELD_MAP: dict[str, str] = {
    "时间": "time_range",
    "起止": "time_range",
    "角色": "role",
    "职位": "role",
    "岗位": "role",
    "个人定位": "role",
    "公司": "organization",
    "组织": "organization",
    "公司/组织": "organization",
    "单位": "organization",
    "地点": "location",
    "项目名称": "project_name",
    "背景": "background",
}

# Fields that should be masked out by default when rendering a resume
# (they belong in 信息.md the personal vault, NOT on a submitted resume).
# See references/application-framing.md "隐私与脱敏" section.
SENSITIVE_BASIC_FIELDS: set[str] = {
    "id_number",       # 身份证号
    "address",         # 详细住址
    "student_id",      # 学号
    "hometown",        # 籍贯 (allow only when target role is 选调/公务员)
    "birth",           # 完整出生年月日（年龄已覆盖）
}


def _lower_strip(k: str) -> str:
    return k.strip().lower()


def normalize_basic_key(key: str) -> str:
    return BASIC_KEY_MAP.get(key.strip(), None) or BASIC_KEY_MAP.get(_lower_strip(key), key.strip())


def normalize_academics_key(key: str) -> str:
    return ACADEMICS_KEY_MAP.get(key.strip(), None) or ACADEMICS_KEY_MAP.get(_lower_strip(key), key.strip())


def normalize_experience_field(key: str) -> str:
    return EXPERIENCE_FIELD_MAP.get(key.strip(), None) or EXPERIENCE_FIELD_MAP.get(_lower_strip(key), key.strip())


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a new profile dict where dict keys use English canonical names.

    - basic/academics: keys translated via BASIC_KEY_MAP / ACADEMICS_KEY_MAP.
    - experiences[].fields: keys translated via EXPERIENCE_FIELD_MAP.
    - Unknown keys pass through unchanged (lenient — never drop user data).
    - Original Chinese keys are also kept, so templates written against either
      naming scheme still work during the transition.
    """
    out: dict[str, Any] = {
        "basic": {},
        "academics": {},
        "project_index": list(profile.get("project_index", [])),
        "experiences": [],
        "student_work": list(profile.get("student_work", [])),
        "skills": list(profile.get("skills", [])),
        "awards": list(profile.get("awards", [])),
        "other": list(profile.get("other", [])),
        "sensitive": dict(profile.get("sensitive", {})),
        "sources": list(profile.get("sources", [])),
        "extras": dict(profile.get("extras", {})),
    }

    for k, v in profile.get("basic", {}).items():
        en = normalize_basic_key(k)
        out["basic"][en] = v
        if en != k:
            out["basic"][k] = v  # keep Chinese alias for legacy templates

    for k, v in profile.get("academics", {}).items():
        en = normalize_academics_key(k)
        out["academics"][en] = v
        if en != k:
            out["academics"][k] = v

    for exp in profile.get("experiences", []):
        new_fields: dict[str, Any] = {}
        for k, v in exp.get("fields", {}).items():
            en = normalize_experience_field(k)
            new_fields[en] = v
            if en != k:
                new_fields[k] = v
        out["experiences"].append({
            "title": exp.get("title", ""),
            "fields": new_fields,
            "bullets": list(exp.get("bullets", [])),
        })

    return out


def sanitize_for_resume(profile: dict[str, Any], target_role: str | None = None) -> dict[str, Any]:
    """Remove sensitive fields from a canonical profile before rendering.

    信息.md is an information vault — it can keep 身份证 / 住址 / 学号 because
    users might need them offline. Resumes go to third parties; by default we
    strip those fields. Selected fields may be re-enabled based on target_role
    (e.g. 籍贯 is expected for 选调/公务员 applications).

    Returns a new dict; the input is not modified.
    """
    import copy
    cleaned = copy.deepcopy(profile)

    allow_hometown = False
    if target_role:
        role_lower = target_role.lower()
        if any(kw in target_role for kw in ("选调", "公务员", "事业单位", "国企", "央企")):
            allow_hometown = True

    for field in SENSITIVE_BASIC_FIELDS:
        if field == "hometown" and allow_hometown:
            continue
        cleaned.get("basic", {}).pop(field, None)
        # also remove Chinese aliases
        for cn, en in BASIC_KEY_MAP.items():
            if en == field:
                cleaned.get("basic", {}).pop(cn, None)

    return cleaned
