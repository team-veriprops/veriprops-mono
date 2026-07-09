"""PageRequest split (DB-2): the flexible query controls must not be bindable from the
wire. A client-facing `PageRequest` carries only pagination; `where`/`order_by`/
`query_fields` live on the server-only `InternalPageRequest`.
"""
from main.appodus_utils import InternalPageRequest, PageRequest

_CONTROL_FIELDS = {"where", "order_by", "query_fields", "exact_string_values"}


def test_page_request_has_no_query_controls():
    fields = set(PageRequest.model_fields.keys())
    assert fields == {"page", "page_size"}
    assert not (_CONTROL_FIELDS & fields)


def test_internal_page_request_carries_controls():
    fields = set(InternalPageRequest.model_fields.keys())
    assert _CONTROL_FIELDS <= fields


def test_client_supplied_controls_are_ignored_on_page_request():
    # extra="ignore" means a client sending where/orderBy to a PageRequest-bound DTO
    # cannot inject them — the fields simply don't exist on the model.
    dto = PageRequest.model_validate(
        {"page": 1, "pageSize": 5, "where": "password_hash like", "orderBy": "id desc"}
    )
    assert not hasattr(dto, "where")
    assert not hasattr(dto, "order_by")
    assert dto.page == 1 and dto.page_size == 5
