"""Shared test fixtures for CSS pod integration tests."""

import pytest
import os
import time
import requests


@pytest.fixture(scope="session")
def css_base_url():
    """Get CSS base URL from environment."""
    return os.environ.get("CSS_BASE_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def css_is_healthy(css_base_url):
    """Check if CSS is healthy before running tests."""
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Try to connect to CSS - any response < 500 indicates it's responding
            response = requests.head(f"{css_base_url}/", timeout=5)
            if response.status_code < 500:
                return True
        except requests.RequestException:
            pass

        retry_count += 1
        if retry_count < max_retries:
            time.sleep(1)

    print(f"\n⚠️  Warning: CSS at {css_base_url} did not respond after {max_retries}s.")
    return False


@pytest.fixture
def agent_identities():
    """Return simulated agent WebID identities."""
    return {
        "ayoub": "http://localhost:3000/ayoub/profile/card#me",
        "claire": "http://localhost:3000/claire/profile/card#me",
        "fatima": "http://localhost:3000/fatima/profile/card#me",
        "marc": "http://localhost:3000/marc/profile/card#me",
        "isabelle": "http://localhost:3000/isabelle/profile/card#me",
        "troll": "http://localhost:3000/troll/profile/card#me",
    }


@pytest.fixture
def pod_names():
    """Return list of expected pod names."""
    return [
        "ayoub",
        "claire-student-1",
        "claire-student-2",
        "fatima-child-1",
        "fatima-child-2",
        "school-community",
    ]


@pytest.fixture
def acl_matrix():
    """Return the complete ACL access matrix.

    Format: pod_name -> agent -> [access_modes]
    where access_modes = ["R", "W", "C"] or [] for no access
    """
    return {
        "ayoub": {
            "ayoub": ["R", "W", "C"],  # owner
            "claire": ["R"],  # tutor
            "fatima": [],  # no access
            "marc": ["R"],  # admin
            "isabelle": ["R"],  # regional
            "troll": [],  # no access
        },
        "claire-student-1": {
            "ayoub": [],  # no access
            "claire": ["R"],  # tutor
            "fatima": [],  # not her child
            "marc": ["R"],  # admin
            "isabelle": ["R"],  # regional
            "troll": [],  # no access
        },
        "claire-student-2": {
            "ayoub": [],
            "claire": ["R"],
            "fatima": [],
            "marc": ["R"],
            "isabelle": ["R"],
            "troll": [],
        },
        "fatima-child-1": {
            "ayoub": [],
            "claire": [],  # not her student
            "fatima": ["R"],  # parent
            "marc": ["R"],  # admin
            "isabelle": ["R"],  # regional
            "troll": [],
        },
        "fatima-child-2": {
            "ayoub": [],
            "claire": [],
            "fatima": ["R"],
            "marc": ["R"],
            "isabelle": ["R"],
            "troll": [],
        },
        "school-community": {
            "ayoub": ["R"],  # student
            "claire": ["R"],  # tutor
            "fatima": ["R"],  # parent
            "marc": ["R", "W", "C"],  # admin
            "isabelle": ["R"],  # regional
            "troll": [],  # no access
        },
    }
