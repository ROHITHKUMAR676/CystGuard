from datetime import date, datetime, timezone

import pytest

from app.clinical.kyoto.schemas import ClinicalContext, EvidenceSource, EvidenceSourceType, Fact, FindingStatus


@pytest.fixture
def context():
    return ClinicalContext(evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc), assessment_date=date(2026, 1, 1))


@pytest.fixture
def evidence():
    return EvidenceSource(source_type=EvidenceSourceType.MRI_REPORT, source_id="synthetic-report-1", field="fixture")


def present(evidence=()):
    return Fact(status=FindingStatus.PRESENT, evidence=tuple(evidence))


def absent(evidence=()):
    return Fact(status=FindingStatus.ABSENT, evidence=tuple(evidence))
