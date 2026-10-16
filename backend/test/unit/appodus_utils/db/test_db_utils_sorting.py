"""Client-driven list sorting and page metadata (`DbUtils.client_order_by`, `build_page`).

A list endpoint lets the client pick a sort only from that list's allowlist of its own
columns: a column outside it would make the sort an oracle over fields the client may not
read. An unknown or malformed sort silently falls back to the list's default, and
`meta.sort` reports the order actually applied so the table header shows the truth.
"""
from sqlalchemy.dialects import postgresql

from main.app.domain.payment.models import Payment, PaymentDto
from main.appodus_utils.db.db_utils import DbUtils

SORTABLE = frozenset({"amount_minor", "status", "date_created"})
DEFAULT = "dateCreated desc"


def _utils() -> DbUtils:
    return DbUtils(model=Payment, query_qto=PaymentDto)


def _sql(clauses) -> list[str]:
    return [str(c.compile(dialect=postgresql.dialect())) for c in clauses]


class TestParseOrderByAllowlist:
    def test_without_allowlist_behaviour_is_unchanged(self):
        """Server-side callers (`_search_rows`) pass snake_case and get no tiebreaker."""
        assert _sql(_utils().parse_order_by_clause("date_created desc, status")) == [
            "payments.date_created DESC", "payments.status ASC",
        ]

    def test_allowlist_accepts_camel_case_wire_keys_and_appends_the_id_tiebreaker(self):
        assert _sql(_utils().parse_order_by_clause("amountMinor desc", SORTABLE)) == [
            "payments.amount_minor DESC", "payments.id ASC",
        ]

    def test_allowlist_drops_columns_outside_it(self):
        assert _utils().parse_order_by_clause("txRef asc", SORTABLE) == []

    def test_allowlist_drops_an_unknown_direction(self):
        assert _utils().parse_order_by_clause("status sideways", SORTABLE) == []


class TestClientOrderBy:
    def test_applies_a_valid_single_column_sort(self):
        applied, clauses = _utils().client_order_by("amountMinor asc", SORTABLE, DEFAULT)
        assert applied == "amountMinor asc"
        assert _sql(clauses) == ["payments.amount_minor ASC", "payments.id ASC"]

    def test_direction_defaults_to_ascending_and_is_case_insensitive(self):
        assert _utils().client_order_by("status", SORTABLE, DEFAULT)[0] == "status asc"
        assert _utils().client_order_by("status DESC", SORTABLE, DEFAULT)[0] == "status desc"

    def test_no_sort_applies_the_default(self):
        applied, clauses = _utils().client_order_by(None, SORTABLE, DEFAULT)
        assert applied == "dateCreated desc"
        assert _sql(clauses) == ["payments.date_created DESC", "payments.id ASC"]

    def test_unknown_column_falls_back_to_the_default(self):
        assert _utils().client_order_by("txRef asc", SORTABLE, DEFAULT)[0] == "dateCreated desc"

    def test_multi_column_and_injection_shaped_input_fall_back_to_the_default(self):
        for raw in ("status asc, amountMinor desc", "status; drop table payments", "id asc", ""):
            assert _utils().client_order_by(raw, SORTABLE, DEFAULT)[0] == "dateCreated desc", raw


class TestBuildPage:
    def test_first_middle_last_and_empty_pages(self):
        first = DbUtils.build_page(["a"] * 10, total=25, page=0, page_size=10).meta
        assert (first.prev_page, first.next_page, first.total_pages) == (None, 1, 3)
        middle = DbUtils.build_page(["a"] * 10, total=25, page=1, page_size=10).meta
        assert (middle.prev_page, middle.next_page) == (0, 2)
        last = DbUtils.build_page(["a"] * 5, total=25, page=2, page_size=10).meta
        assert (last.prev_page, last.next_page, last.count) == (1, None, 5)
        empty = DbUtils.build_page([], total=0, page=0, page_size=10).meta
        assert (empty.prev_page, empty.next_page, empty.total_pages) == (None, None, 0)

    def test_zero_page_size_does_not_divide_by_zero(self):
        meta = DbUtils.build_page([], total=5, page=0, page_size=0).meta
        assert (meta.total_pages, meta.next_page) == (0, None)

    def test_reports_the_applied_sort_and_the_sortable_fields_in_camel_case(self):
        meta = DbUtils.build_page([], total=0, page=0, page_size=10, sort="amountMinor asc", sortable=SORTABLE).meta
        assert meta.sort == "amountMinor asc"
        assert meta.sortable_fields == ["amountMinor", "dateCreated", "status"]

    def test_unsorted_lists_report_no_sort(self):
        meta = DbUtils.build_page([], total=0, page=0, page_size=10).meta
        assert (meta.sort, meta.sortable_fields) == (None, [])
