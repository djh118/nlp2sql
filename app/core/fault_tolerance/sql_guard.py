import re
from typing import Tuple

from app.core.context import request_id_ctx_var
from app.core.fault_tolerance.langfuse_reporter import report_fault_event

SELECT_STAR_PATTERN = re.compile(r"\bselect\s+\*\s*from\b", re.IGNORECASE)
NON_SELECT_PATTERN = re.compile(r"\b(insert|update|delete|drop|truncate|alter|create|replace|load|merge)\b", re.IGNORECASE)
COMMENT_PATTERN = re.compile(r"/\*.*?\*/|--.*?$|#.*?$", re.MULTILINE)


def sanitize_sql(sql: str) -> str:
    return COMMENT_PATTERN.sub("", sql).strip()


def guard_sql(sql: str, block_select_star: bool = True, block_no_where: bool = True) -> Tuple[bool, str]:
    sql = sanitize_sql(sql)
    sql_stripped = sql.strip().strip(";")

    if not sql_stripped:
        return False, "SQL 语句为空"

    if NON_SELECT_PATTERN.search(sql_stripped):
        _report_guard("non_select", sql_stripped)
        return False, "非法操作: 仅允许 SELECT 查询语句"

    if block_select_star and SELECT_STAR_PATTERN.search(sql_stripped):
        _report_guard("select_star", sql_stripped)
        return False, "安全拦截: 禁止使用 SELECT *，请明确指定查询字段"

    if block_no_where and _has_no_where(sql_stripped):
        _report_guard("no_where", sql_stripped)
        return False, "安全拦截: 缺少 WHERE 条件，禁止全表扫描"

    if _is_cartesian_product(sql_stripped):
        _report_guard("cartesian_product", sql_stripped)
        return False, "安全拦截: 检测到多表笛卡尔积，请添加 JOIN 条件"

    return True, ""


def _report_guard(reason: str, sql: str):
    report_fault_event(
        category="sql_guard",
        level="block",
        tag=f"sql_guard/{reason}",
        message=f"SQL 安全拦截 [{reason}]: {sql[:200]}",
        request_id=request_id_ctx_var.get(""),
        metadata={"reason": reason, "sql": sql[:500]},
    )


def _has_no_where(sql: str) -> bool:
    parts = sql.lower().split()
    has_from = False
    from_idx = -1
    for i, token in enumerate(parts):
        if token == "from":
            has_from = True
            from_idx = i
        if token == "where":
            return False
    if not has_from:
        return False
    from_portion = " ".join(parts[from_idx:])
    join_count = len(re.findall(r"\bjoin\b", from_portion))
    on_count = len(re.findall(r"\bon\b", from_portion))
    if join_count > 0 and join_count == on_count:
        return False
    return True


def _is_cartesian_product(sql: str) -> bool:
    lower = sql.lower()
    from_idx = lower.find("from")
    if from_idx == -1:
        return False
    from_clause = lower[from_idx:]
    where_idx = from_clause.find("where")
    if where_idx != -1:
        return False
    from_part = from_clause

    tables = [t.strip() for t in from_part.replace("from", "").split(",")]
    tables = [t for t in tables if t and not t.isspace()]
    if len(tables) > 1 and "join" not in from_part:
        return True

    join_count = len(re.findall(r"\bjoin\b", from_part))
    if join_count > 0:
        on_count = len(re.findall(r"\bon\b", from_part))
        if join_count > on_count:
            return True

    return False
