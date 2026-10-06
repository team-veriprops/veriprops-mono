"""DbUtils `where`-clause parsing → flat SQLAlchemy criterion list.

The criterion list is applied as ``select().where(*criterion)`` — every element
must be a BinaryExpression. A nested list (the old ``append`` of the parsed
conditions) fails SQL coercion at runtime for ANY Search DTO carrying a
``where`` string, which is exactly how sweep queries select their batches.
"""
from datetime import datetime, timezone

from sqlalchemy.sql.elements import BinaryExpression

from main.app.config.settings import IntegratedPlatform
from main.app.domain.message.models import Message, QueryMessageDto, SearchMessageDto
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.domain.webhook.callback.model import Callback, QueryCallbackDto, SearchCallbackDto
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

    def test_a_platform_filter_applies(self):
        """`platform` is a real column on callbacks. It used to sit in the exclusion set beside the
        paging controls, so a search by platform silently returned every platform's rows."""
        criterion = DbUtils(model=Callback, query_qto=QueryCallbackDto).build_search_criterion(
            SearchCallbackDto(platform=IntegratedPlatform.ZOHO_DOC_SIGN)
        )
        rendered = [str(c.compile(compile_kwargs={"literal_binds": True})) for c in criterion]
        assert f"callbacks.platform = '{IntegratedPlatform.ZOHO_DOC_SIGN.value}'" in rendered

    def test_paging_controls_never_become_column_filters(self):
        criterion = _criterion(SearchMessageDto(page=3, page_size=50, status=MessageStatus.FAILED))
        rendered = " | ".join(str(c) for c in criterion)
        assert "page" not in rendered

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
