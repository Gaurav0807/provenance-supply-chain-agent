import pytest

from agent.sql_guard import UnsafeSQL, check


def test_adds_limit_to_select():
    assert check("SELECT 1") == "SELECT 1 LIMIT 1000"


def test_keeps_existing_limit():
    assert check("SELECT 1 LIMIT 5") == "SELECT 1 LIMIT 5"


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE x",
        "DELETE FROM x",
        "INSERT INTO x VALUES (1)",
        "UPDATE x SET a = 1",
        "SELECT 1; DROP TABLE x",
        "SELECT * FROM x -- ; DROP",
    ],
)
def test_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSQL):
        check(sql)
