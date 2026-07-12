"""DbUtils `where`-clause parsing → flat SQLAlchemy criterion list.

The criterion list is applied as ``select().where(*criterion)`` — every element
must be a BinaryExpression. A nested list (the old ``append`` of the parsed
conditions) fails SQL coercion at runtime for ANY Search DTO carrying a
``where`` string, which is exactly how sweep queries select their batches.
"""
from datetime import datetime, timezone

from sqlalchemy.sql.elements import BinaryExpression

from main.app.domain.message.models import Message, QueryMessageDto, SearchMessageDto
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.integrations.messaging.models import MessageStatus


def _criterion(search_dto):
    return DbUtils(model=Message, query_qto=QueryMessageDto).build_search_criterion(search_dto)


class TestWhereCriterion:
    def test_where_conditions_are_flat_expressions(self):
        criterion = _criterion(SearchMessageDto(
            page=0, page_size=100,
            status=MessageStatus.RETRYING,
            next_retry_at=datetime.now(timezone.utc),
            order_by="next_retry_at",
            where="next_retry_at <= ",
        ))
        assert criterion, "criterion list must not be empty"
        assert all(isinstance(c, BinaryExpression) for c in criterion), \
            f"nested/non-expression element in criterion: {[type(c) for c in criterion]}"

    def test_where_field_excluded_from_equality_conditions(self):
        """A field consumed by `where` must not also emit an equality condition."""
        when = datetime.now(timezone.utc)
        criterion = _criterion(SearchMessageDto(
            page=0, page_size=100,
            status=MessageStatus.RETRYING,
            next_retry_at=when,
            where="next_retry_at <= ",
        ))
        rendered = [str(c) for c in criterion]
        assert sum("next_retry_at" in c for c in rendered) == 1

    def test_multiple_comma_separated_conditions(self):
        criterion = _criterion(SearchMessageDto(
            page=0, page_size=100,
            status=MessageStatus.FAILED,
            retry_count=3,
            next_retry_at=datetime.now(timezone.utc),
            where="retry_count <, next_retry_at <= ",
        ))
        assert all(isinstance(c, BinaryExpression) for c in criterion)
        rendered = " | ".join(str(c) for c in criterion)
        assert "retry_count <" in rendered and "next_retry_at <=" in rendered
