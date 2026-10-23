from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass(frozen=True)
class Metric:
    host: str
    key: str
    value: Any
    timestamp: int


@dataclass(frozen=True)
class Target:
    kind: str
    address: str
    name: str
    namespace: Optional[str] = None
    port: Optional[int] = None
    duration: int = 50
    timeout: int = 1


@dataclass
class CollectionResult:
    metrics: List[Metric] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
