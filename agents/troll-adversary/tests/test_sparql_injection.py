"""Unit tests for the SPARQL parameterization engine (Story 2.7).

Tests:
  1. Clean parameter values produce valid SPARQL (AC-2)
  2. Each injection payload category is rejected (AC-2, AC-3)
  3. Determinism: same inputs → same result (AC-6 / NFR12)
  4. Template loading (AC-7)
  5. Parameter extraction (AC-7)

Run from repo root with venv active:
    pytest agents/troll-adversary/tests/test_sparql_injection.py -v
"""

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load parameterize.py via importlib (hyphen in directory name)
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parents[3]  # pocpod0/
_param_path = _repo_root / "agents" / "skills" / "sparql-query" / "parameterize.py"
_spec = importlib.util.spec_from_file_location("parameterize", _param_path)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

load_template = _mod.load_template
parameterize_query = _mod.parameterize_query
extract_params = _mod.extract_params

TEMPLATE_DIR = _repo_root / "agents" / "skills" / "sparql-query" / "templates"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def student_template():
    return load_template("student-progress", TEMPLATE_DIR)


@pytest.fixture
def all_templates():
    names = [
        "student-progress",
        "cross-context-query",
        "aggregate-anonymized",
        "parental-view",
        "transfer-profile",
    ]
    return {name: load_template(name, TEMPLATE_DIR) for name in names}


SAFE_VALUES = {
    "student_uri": "http://localhost:3000/ayoub/profile/card#me",
    "context_uri": "http://localhost:3000/ayoub/",
    "agent_role": "teacher",
    "pod_uri": "http://localhost:3000/ayoub/",
    "program_uri": "http://example.org/program/math",
    "community_uri": "http://localhost:3000/school-community/",
    "parent_uri": "http://localhost:3000/fatima/profile/card#me",
    "child_uri": "http://localhost:3000/fatima-child-1/profile/card#me",
    "school_uri": "http://example.org/school/brussels-1",
}


# ---------------------------------------------------------------------------
# AC-2: Clean values produce valid SPARQL
# ---------------------------------------------------------------------------

class TestCleanSubstitution:
    def test_student_progress_produces_valid_sparql(self, student_template):
        """Clean URI parameters are substituted correctly."""
        params = {
            "student_uri": "http://localhost:3000/ayoub/profile/card#me",
            "context_uri": "http://localhost:3000/ayoub/",
        }
        result = parameterize_query(student_template, params)
        assert "<http://localhost:3000/ayoub/profile/card#me>" in result
        assert "<http://localhost:3000/ayoub/>" in result
        assert "$student_uri" not in result
        assert "$context_uri" not in result

    def test_plain_string_param_gets_quoted(self, all_templates):
        """Non-URI safe strings are double-quoted in output."""
        template = all_templates["cross-context-query"]
        params = {
            "agent_role": "teacher",
            "pod_uri": "http://localhost:3000/ayoub/",
        }
        result = parameterize_query(template, params)
        assert '"teacher"' in result

    def test_all_templates_accept_safe_values(self, all_templates):
        """Every template accepts safe parameter values without error."""
        for name, template in all_templates.items():
            params_needed = extract_params(template)
            params = {p: SAFE_VALUES.get(p, f"http://example.org/{p}") for p in params_needed}
            result = parameterize_query(template, params)
            # No unresolved placeholders remain
            for p in params_needed:
                assert f"${p}" not in result, f"Unresolved placeholder ${p} in {name}"

    def test_missing_param_raises_key_error(self, student_template):
        """Missing required parameters raise KeyError."""
        with pytest.raises(KeyError):
            parameterize_query(student_template, {"student_uri": "http://example.org/x"})
            # context_uri is missing


# ---------------------------------------------------------------------------
# AC-2 / AC-3: Injection payloads are rejected
# ---------------------------------------------------------------------------

class TestInjectionRejection:
    """Each injection category must be rejected by the parameterization engine."""

    CLAUSE_INJECTION = [
        "; DROP ALL",
        "} UNION { SELECT * WHERE { ?s ?p ?o } }",
        "OPTIONAL { ?secret <http://secret> ?value }",
    ]

    STRING_ESCAPE = [
        'value" . ?s ?p ?o . FILTER(?o = "secret',
        "value\\",
        "value' ; --",
    ]

    URI_INJECTION = [
        # These look like URIs but contain injection chars
        "http://evil.com> . OPTIONAL { ?s ?p ?o } . <http://x",
    ]

    COMMENT_INJECTION = [
        "value # rest of query is commented out",
        "value\n# comment\n",
    ]

    FILTER_INJECTION = [
        'value" FILTER(true) . ?admin <http://role> "admin',
        "value FILTER(?role = <http://admin>)",
    ]

    NESTED_QUERY = [
        "{ SELECT * WHERE { ?s ?p ?o } }",
        "value } { SELECT * WHERE { ?s ?p ?o } } {",
    ]

    def _inject(self, template, param_name, payload):
        params_needed = extract_params(template)
        params = {p: SAFE_VALUES.get(p, f"http://example.org/{p}") for p in params_needed}
        params[param_name] = payload
        return parameterize_query(template, params)

    @pytest.mark.parametrize("payload", CLAUSE_INJECTION)
    def test_clause_injection_rejected(self, student_template, payload):
        with pytest.raises((ValueError, KeyError)):
            self._inject(student_template, "student_uri", payload)

    @pytest.mark.parametrize("payload", STRING_ESCAPE)
    def test_string_escape_rejected(self, student_template, payload):
        with pytest.raises((ValueError, KeyError)):
            self._inject(student_template, "student_uri", payload)

    @pytest.mark.parametrize("payload", URI_INJECTION)
    def test_uri_injection_rejected(self, student_template, payload):
        with pytest.raises((ValueError, KeyError)):
            self._inject(student_template, "student_uri", payload)

    @pytest.mark.parametrize("payload", COMMENT_INJECTION)
    def test_comment_injection_rejected(self, student_template, payload):
        with pytest.raises((ValueError, KeyError)):
            self._inject(student_template, "student_uri", payload)

    @pytest.mark.parametrize("payload", FILTER_INJECTION)
    def test_filter_injection_rejected(self, student_template, payload):
        with pytest.raises((ValueError, KeyError)):
            self._inject(student_template, "student_uri", payload)

    @pytest.mark.parametrize("payload", NESTED_QUERY)
    def test_nested_query_rejected(self, student_template, payload):
        with pytest.raises((ValueError, KeyError)):
            self._inject(student_template, "student_uri", payload)

    def test_sparql_keyword_union_rejected(self, student_template):
        with pytest.raises(ValueError, match="UNION"):
            self._inject(student_template, "student_uri", "UNION SELECT * WHERE")

    def test_sparql_keyword_drop_rejected(self, student_template):
        with pytest.raises(ValueError, match="DROP"):
            self._inject(student_template, "student_uri", "DROP ALL")

    def test_sparql_keyword_filter_rejected(self, student_template):
        with pytest.raises(ValueError, match="FILTER"):
            self._inject(student_template, "student_uri", "FILTER(true)")

    def test_empty_value_rejected(self, student_template):
        with pytest.raises(ValueError, match="empty"):
            self._inject(student_template, "student_uri", "")


# ---------------------------------------------------------------------------
# AC-6 / NFR12: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_inputs_same_output(self, student_template):
        """Same template + same params → identical output every call."""
        params = {
            "student_uri": "http://localhost:3000/ayoub/profile/card#me",
            "context_uri": "http://localhost:3000/ayoub/",
        }
        results = [parameterize_query(student_template, params) for _ in range(10)]
        assert len(set(results)) == 1, "Non-deterministic output detected"

    def test_same_rejection_every_run(self, student_template):
        """Same injection payload → always rejected, same error type."""
        payload = "; DROP ALL"
        params = {
            "student_uri": payload,
            "context_uri": "http://localhost:3000/ayoub/",
        }
        errors = []
        for _ in range(5):
            try:
                parameterize_query(student_template, params)
                errors.append(None)
            except (ValueError, KeyError) as exc:
                errors.append(type(exc).__name__)
        assert all(e == errors[0] for e in errors), "Non-deterministic rejection"
        assert errors[0] is not None, "Injection was not rejected"


# ---------------------------------------------------------------------------
# AC-7: Template loading and parameter extraction
# ---------------------------------------------------------------------------

class TestTemplateLoading:
    def test_all_templates_loadable(self):
        names = [
            "student-progress",
            "cross-context-query",
            "aggregate-anonymized",
            "parental-view",
            "transfer-profile",
        ]
        for name in names:
            template = load_template(name, TEMPLATE_DIR)
            assert len(template) > 0, f"Template {name} is empty"

    def test_template_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent-template", TEMPLATE_DIR)

    def test_extract_params_student_progress(self):
        template = load_template("student-progress", TEMPLATE_DIR)
        params = extract_params(template)
        assert "student_uri" in params
        assert "context_uri" in params

    def test_extract_params_cross_context(self):
        template = load_template("cross-context-query", TEMPLATE_DIR)
        params = extract_params(template)
        assert "agent_role" in params
        assert "pod_uri" in params

    def test_templates_have_dollar_placeholders(self):
        """Templates use $param syntax, not {param} or %(param)s."""
        for name in ["student-progress", "parental-view", "transfer-profile"]:
            template = load_template(name, TEMPLATE_DIR)
            params = extract_params(template)
            assert len(params) >= 1, f"Template {name} has no parameters"
            for p in params:
                assert f"${p}" in template, f"${p} not found in {name}"
