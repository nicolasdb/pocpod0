# conftest.py — pytest configuration for SPARQL skill tests.
# Ensures handler.py (in parent directory) is on sys.path.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
