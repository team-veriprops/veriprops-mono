"""`contains_text`: a typed search matches what was typed, never a wildcard pattern.

A raw ``ilike(f"%{q}%")`` lets a search for ``%`` or ``_`` match every row, so an admin
looking for a literal underscore in an email sees the whole table. Every search box goes
through the one helper, which escapes the typed text; the guard below fails on a new raw
``ilike`` under ``main/app``.
"""
import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from main.app.domain.user.models import User
from main.appodus_utils.db.search import contains_text


def _sql(criterion) -> str:
    stmt = select(User.id).where(criterion)
    return " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).lower().split())


def test_blank_or_missing_text_adds_no_condition():
    assert contains_text(None, User.email) is None
    assert contains_text("   ", User.email) is None


def test_it_matches_any_column_case_insensitively_on_the_trimmed_text():
    sql = _sql(contains_text("  Ada ", User.first_name, User.email))

    assert "lower(users.first_name) like '%' || lower('ada') || '%' escape '/'" in sql
    assert "lower(users.email) like '%' || lower('ada') || '%' escape '/'" in sql
    assert " or " in sql


def test_typed_wildcards_are_literal_characters():
    sql = _sql(contains_text("50%_off", User.email))

    assert "lower('50/%/_off')" in sql and "escape '/'" in sql


def test_postgres_runs_it_as_an_escaped_ilike():
    stmt = select(User.id).where(contains_text("a_b", User.email))
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    assert "users.email ILIKE '%%' || 'a/_b' || '%%' ESCAPE '/'" in sql


def test_it_accepts_a_computed_expression():
    full_name = func.concat(User.first_name, " ", User.last_name)

    sql = _sql(contains_text("ada obi", full_name))

    assert "lower(concat(users.first_name, ' ', users.last_name)) like" in sql


_APP_ROOT = Path(__file__).resolve().parents[4] / "main" / "app"
_RAW_ILIKE = re.compile(r"\.ilike\(")


def test_no_app_search_builds_its_own_unescaped_pattern():
    offenders = [
        f"{path.relative_to(_APP_ROOT)}:{n}"
        for path in _APP_ROOT.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _RAW_ILIKE.search(line)
    ]
    assert offenders == [], f"use appodus_utils.db.search.contains_text instead: {offenders}"
