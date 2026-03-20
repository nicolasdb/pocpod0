"""SPARQL query template parameterization engine.

Security boundary for SEC-3: prevents SPARQL injection by validating and
safely substituting $parameter placeholders in .rq template files.

This module is shared between:
  - Story 2.7: troll injection tests
  - Story 3.1: shared SPARQL skill runtime

Design contract:
  - Templates use $parameter_name syntax (dollar-sign prefix, snake_case)
  - Parameters are substituted as URI references: <value>
  - String literal parameters are escaped and quoted: "value"
  - Injection patterns are rejected before substitution
  - No string concatenation — substitution only through this module
"""

import re
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Template directory (default, overridable in tests and CLI)
# ---------------------------------------------------------------------------

_DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"

# ---------------------------------------------------------------------------
# Injection detection patterns
# ---------------------------------------------------------------------------

# SPARQL keywords that should never appear in parameter values
_SPARQL_KEYWORDS = frozenset([
    "SELECT", "INSERT", "DELETE", "WHERE", "FILTER", "OPTIONAL",
    "UNION", "GRAPH", "ASK", "CONSTRUCT", "DESCRIBE", "PREFIX",
    "BASE", "FROM", "NAMED", "ORDER", "GROUP", "HAVING", "LIMIT",
    "OFFSET", "DISTINCT", "REDUCED", "AS", "BY", "NOT", "IN",
    "EXISTS", "BIND", "VALUES", "SERVICE", "MINUS", "DROP", "CLEAR",
    "CREATE", "ADD", "MOVE", "COPY", "LOAD", "ALL",
])

# Injection indicators for non-URI string values
_STRING_INJECTION_PATTERNS = [
    re.compile(r";"),                          # clause terminator
    re.compile(r"#"),                          # SPARQL comment (only dangerous in strings)
    re.compile(r"\{"),                         # nested block open
    re.compile(r"\}"),                         # nested block close
    re.compile(r'"'),                          # unescaped double quote
    re.compile(r"'"),                          # unescaped single quote
    re.compile(r"\\"),                         # backslash escape
    re.compile(r"\n"),                         # newline (comment injection)
]

# Injection indicators that apply even to URI values
# (# fragment is valid in URIs so is NOT in this list)
_URI_INJECTION_PATTERNS = [
    re.compile(r";"),                          # clause terminator
    re.compile(r"\{"),                         # nested block open
    re.compile(r"\}"),                         # nested block close
    re.compile(r'"'),                          # unescaped double quote
    re.compile(r"'"),                          # unescaped single quote
    re.compile(r"\\"),                         # backslash escape
    re.compile(r"\n"),                         # newline
    re.compile(r"\s"),                         # whitespace in URIs is always invalid
]

# Placeholder pattern: $word_chars only
_PLACEHOLDER_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")

# URI pattern: must look like a URI (scheme://...) or a relative path
# We intentionally allow only URI-safe characters
_URI_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://[^\s<>\"{}|\\^`\[\]]+$")

# Allowed plain string pattern (for non-URI values): alphanumeric + safe chars
_SAFE_STRING_RE = re.compile(r"^[a-zA-Z0-9_\-\.\:/@ ]+$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_template(template_name: str, template_dir: Optional[Path] = None) -> str:
    """Load a .rq template file by name.

    Args:
        template_name: Base name of the template (with or without .rq extension).
        template_dir: Directory to search (defaults to templates/ sibling dir).

    Returns:
        Template content as a string.

    Raises:
        FileNotFoundError: If template does not exist.
    """
    directory = template_dir or _DEFAULT_TEMPLATE_DIR
    name = template_name if template_name.endswith(".rq") else f"{template_name}.rq"
    path = Path(directory) / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8")


def parameterize_query(template: str, params: dict[str, str]) -> str:
    """Safely substitute $parameter placeholders in a SPARQL template.

    This is the security boundary (SEC-3). Each parameter value is validated
    before substitution. Any value that contains injection patterns is rejected
    with a ValueError.

    Args:
        template: SPARQL template string with $parameter placeholders.
        params: Mapping of parameter name → value to substitute.

    Returns:
        SPARQL query string with all placeholders replaced.

    Raises:
        ValueError: If a parameter value fails injection validation.
        KeyError: If a placeholder in the template has no corresponding param.
    """
    # Discover all placeholders in template
    declared_params = set(_PLACEHOLDER_RE.findall(template))

    # Validate: all placeholders must be provided
    missing = declared_params - set(params.keys())
    if missing:
        raise KeyError(f"Missing parameters for template: {sorted(missing)}")

    # Validate and encode each provided value
    encoded: dict[str, str] = {}
    for name, value in params.items():
        if name not in declared_params:
            # Extra params are silently ignored (defense in depth: don't leak)
            continue
        _validate_param_value(name, value)
        encoded[name] = _encode_param_value(value)

    # Substitute: replace $name with encoded value
    result = template
    # Sort by length descending to avoid partial substitution ($foo before $foobar)
    for name in sorted(encoded.keys(), key=len, reverse=True):
        result = result.replace(f"${name}", encoded[name])

    return result


def extract_params(template: str) -> list[str]:
    """Return the list of $parameter names declared in a template.

    Args:
        template: SPARQL template string.

    Returns:
        Sorted list of parameter names (without $ prefix).
    """
    return sorted(set(_PLACEHOLDER_RE.findall(template)))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_param_value(name: str, value: str) -> None:
    """Validate that a parameter value does not contain injection patterns.

    URIs and plain strings are handled separately:
    - URIs: allow # fragments but reject whitespace, braces, semicolons etc.
    - Plain strings: reject #, quotes, semicolons, braces, backslash, newline.

    Raises ValueError with a descriptive message if injection is detected.
    """
    if not value:
        raise ValueError(f"Parameter '{name}' must not be empty")

    is_uri = bool(_URI_RE.match(value))
    injection_patterns = _URI_INJECTION_PATTERNS if is_uri else _STRING_INJECTION_PATTERNS

    # Check for SPARQL keywords (case-insensitive, whole-word match)
    # Skip keyword check for URIs — SPARQL keywords appear legitimately in vocabularies
    # e.g. <https://data.vlaanderen.be/ns/onderwijs#base>
    if not is_uri:
        value_upper = value.upper()
        for keyword in _SPARQL_KEYWORDS:
            if re.search(r"(?<![A-Z])" + keyword + r"(?![A-Z])", value_upper):
                raise ValueError(
                    f"Parameter '{name}' contains SPARQL keyword '{keyword}': {value!r}"
                )

    # Check for injection characters
    for pattern in injection_patterns:
        if pattern.search(value):
            raise ValueError(
                f"Parameter '{name}' contains injection character "
                f"(pattern={pattern.pattern!r}): {value!r}"
            )

    # Final check: must match URI or safe string pattern
    if not (is_uri or _SAFE_STRING_RE.match(value)):
        raise ValueError(
            f"Parameter '{name}' does not match allowed URI or safe-string pattern: {value!r}"
        )


def _encode_param_value(value: str) -> str:
    """Encode a validated parameter value for safe SPARQL substitution.

    URIs are wrapped in angle brackets: <uri>
    Plain strings are double-quoted: "value"
    """
    if _URI_RE.match(value):
        return f"<{value}>"
    # Plain safe string
    return f'"{value}"'
