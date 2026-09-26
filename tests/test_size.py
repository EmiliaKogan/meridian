"""The size gate: every function in src/meridian <= 20 code lines, every file <= 250."""

#from tools.check_loc import find_violations
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from check_loc import find_violations

def test_src_is_small():
    violations = find_violations(["src/meridian"])
    assert not violations, "\n".join(violations)
