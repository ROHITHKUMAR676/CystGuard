from collections.abc import Iterable

from app.clinical.kyoto.schemas import EvidenceSource


def unique_evidence(*groups: Iterable[EvidenceSource]) -> tuple[EvidenceSource, ...]:
    """Return provenance in first-seen order without inventing source details."""
    results: list[EvidenceSource] = []
    seen: set[EvidenceSource] = set()
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                results.append(item)
    return tuple(results)
