"""Troll adversary attack modules.

Exports shared data model for use within the attacks package.
Future attack categories (sparql-injection, vector-privacy, etc.) import from here.
"""

from .acl_enforcement import TrollTestResult, log_test_result

__all__ = ["TrollTestResult", "log_test_result"]
