"""Regression: JSON columns must accept their native Python type on attribute-set.

Guards against the shared-``JSONB_VARIANT``-instance bug: ``Mutable.as_mutable`` installs a
*process-global* listener that binds its coercion to every mapped column whose type *is the same
instance*. When one shared ``JSONB_VARIANT`` was reused across dict, list, and plain JSON columns,
``MutableList`` coercion leaked onto dict columns (and only the first listener won per column), so
persisting an ``audit_logs.details`` dict raised:

    Attribute 'details' does not accept objects of type <class 'dict'>

Each mutable column now uses its own ``jsonb_variant()`` instance, scoping the listener to that one
column. The coercion runs on attribute assignment, so these checks need no database round-trip —
the previous mock-repo tests never exercised this path, which is why the bug shipped.
"""
import main.app.domain  # noqa: F401  — aggregate import registers every ORM mapper
from sqlalchemy.orm import configure_mappers

from main.app.domain.audit.models import AuditActionType, AuditLog
from main.app.domain.property.models import Property
from main.app.domain.user.agent.profile.models import AgentProfile
from main.app.domain.user.models import User

# Force the mutable listeners to bind against every mapper before the assertions run.
configure_mappers()


def test_dict_json_columns_accept_dicts():
    details = {"tier": "STANDARD", "weights": {"REGISTRY": 40, "FIELD": 30, "SURVEYOR": 30}}
    log = AuditLog(action=AuditActionType.ADMIN_CONFIG_CHANGED.value, details=details)
    assert log.details == details

    prop = Property(
        customer_id="c1",
        property_type="LAND",
        details={"size_sqm": 500},
        seller={"name": "Ada"},
        documents=[{"kind": "survey_plan"}],
    )
    assert prop.details == {"size_sqm": 500}
    assert prop.seller == {"name": "Ada"}
    assert prop.documents == [{"kind": "survey_plan"}]


def test_list_json_columns_accept_lists():
    user = User(personas=["CUSTOMER", "AGENT"])
    assert user.personas == ["CUSTOMER", "AGENT"]

    profile = AgentProfile(roles=["FIELD"], approved_roles=[])
    assert profile.roles == ["FIELD"]
    assert profile.approved_roles == []
