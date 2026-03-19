"""Shared pytest fixtures for pipeline tests."""

import pytest
from pathlib import Path


@pytest.fixture
def schemas_dir() -> Path:
    """Return path to the data/schemas directory."""
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "data" / "schemas"


@pytest.fixture
def oslo_education_ttl(schemas_dir: Path) -> Path:
    return schemas_dir / "oslo-education.ttl"


@pytest.fixture
def oslo_person_ttl(schemas_dir: Path) -> Path:
    return schemas_dir / "oslo-person.ttl"


@pytest.fixture
def xapi_to_oslo_ttl(schemas_dir: Path) -> Path:
    return schemas_dir / "xapi-to-oslo.ttl"


@pytest.fixture
def pocpod0_vocab_ttl(schemas_dir: Path) -> Path:
    return schemas_dir / "pocpod0-vocab.ttl"


@pytest.fixture
def all_schema_files(
    oslo_education_ttl, oslo_person_ttl, xapi_to_oslo_ttl, pocpod0_vocab_ttl
):
    return [oslo_education_ttl, oslo_person_ttl, xapi_to_oslo_ttl, pocpod0_vocab_ttl]
