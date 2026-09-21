"""Subclass auto-registration (`BaseDiBootstrap.register_all_subclasses`).

The messaging layer registers providers by walking `IMessageProvider.__subclasses__()` at
import time. That walk runs while the provider package is still importing, so which
concrete classes are visible depends on import order — and an abstract intermediate with
no visible implementation must not be treated as something to instantiate.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from kink import inject

from main.appodus_utils.config.bootstrap import BaseDiBootstrap


class _Base(ABC):
    @abstractmethod
    def run(self) -> str: ...


class _AbstractMiddle(_Base):
    """Abstract intermediate whose implementations are not imported yet."""

    @abstractmethod
    def extra(self) -> str: ...


@inject
class _Concrete(_Base):
    def run(self) -> str:
        return "concrete"


class TestSubclassInstances:
    def test_collects_concrete_subclasses(self):
        instances = BaseDiBootstrap._get_all_subclasses_instances(_Base)
        assert any(isinstance(i, _Concrete) for i in instances)

    def test_skips_an_abstract_intermediate_with_no_visible_implementation(self):
        # Asking the container for it used to raise, making startup depend on the order
        # in which provider modules happened to be imported.
        instances = BaseDiBootstrap._get_all_subclasses_instances(_Base)
        assert all(not isinstance(i, _AbstractMiddle) for i in instances)

    def test_recurses_into_an_intermediate_once_an_implementation_exists(self):
        @inject
        class _Impl(_AbstractMiddle):
            def run(self) -> str:
                return "impl"

            def extra(self) -> str:
                return "extra"

        instances = BaseDiBootstrap._get_all_subclasses_instances(_Base)
        assert any(isinstance(i, _Impl) for i in instances)
