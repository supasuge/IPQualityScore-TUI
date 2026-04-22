import sys
from pathlib import Path

# Make `ipqs_tui` importable as a package from the project root's parent.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))