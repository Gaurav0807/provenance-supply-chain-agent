"""Safety check for SQL before it runs.

Only one read-only SELECT is allowed, and it may read only the tables the ontology maps to concepts.
"""
import re

from agent.ontology_lookup import allowed_tables

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|grant|revoke|merge|truncate|unload|copy|call|msck)\b",
    re.IGNORECASE,
)
TABLE_REFERENCE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][\w.]*)", re.IGNORECASE)


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

    allowed = allowed_tables()
    for table in TABLE_REFERENCE.findall(s):
        if table.lower() not in allowed:
            raise UnsafeSQL(f"table not allowed: {table}")

    if not re.search(r"\blimit\s+\d+", s, re.IGNORECASE):
        s += f" LIMIT {max_rows}"
    return s
