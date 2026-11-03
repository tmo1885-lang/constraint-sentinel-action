"""Start the composite Action with imports restricted to trusted locations."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from constraint_sentinel.cli import main

raise SystemExit(main())
