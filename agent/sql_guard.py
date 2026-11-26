"""Safety check for SQL before it runs. Only a single read-only SELECT gets through."""
import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|grant|revoke|merge|truncate|unload|copy|call|msck)\b",
    re.IGNORECASE,
)


class UnsafeSQL(Exception):
    pass


def check(sql, max_rows=1000):
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise UnsafeSQL("only one statement is allowed")
    if not re.match(r"^(select|with)\b", s, re.IGNORECASE):
        raise UnsafeSQL("only SELECT queries are allowed")
    if FORBIDDEN.search(s):
        raise UnsafeSQL("write or admin keyword found")
    if not re.search(r"\blimit\s+\d+", s, re.IGNORECASE):
        s += f" LIMIT {max_rows}"
    return s
