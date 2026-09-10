"""BaseAdapter — the contract every data-source adapter implements.

See PRD v1.2 A5.2 for rules. One adapter pulls from one source; the
engine composes adapters into a module via the industry config.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Iterable

from .models import Post, SourceClass


class BaseAdapter(ABC):
    """Every concrete adapter subclasses this.

    Subclass-level metadata (set as class vars, not instance vars) lets
    the engine introspect adapters without instantiating them.
    """

    adapter_id: ClassVar[str]
    source_class: ClassVar[SourceClass]
    tier: ClassVar[str]           # "A" | "B" | "C" | "D" per PRD A8
    tos_basis: ClassVar[str]      # required; engine rejects empty

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Skip enforcement on abstract intermediates (they'll set these
        # themselves in their own concrete subclasses).
        if getattr(cls, "__abstractmethods__", None):
            return
        required = ("adapter_id", "source_class", "tier", "tos_basis")
        for name in required:
            if not getattr(cls, name, None):
                raise TypeError(
                    f"{cls.__name__} must set class var '{name}' "
                    f"(PRD v1.2 A5.2 / A9.4)."
                )

    @abstractmethod
    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        """Yield Posts observed since `since`.

        `cursor` is an adapter-private pagination/resume token. Adapters
        that don't paginate can ignore it.
        """
        ...
