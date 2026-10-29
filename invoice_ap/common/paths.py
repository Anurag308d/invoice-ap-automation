"""Repository-relative default locations (pathlib only, so paths work on every OS)."""
from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_DIR.parent
DEFAULT_POLICY = REPO_ROOT / "config" / "ap_policy.toml"
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"
SPEC_JSON = PACKAGE_DIR / "spec" / "data_dictionary.json"

# Dataset layout inside data/<scale>/ (see docs/architecture.md). The engine may read only
# ENGINE_READABLE layers; EVALUATION_ONLY layers are for the evaluation and quality modules.
LAYERS = ("master", "inbox", "source", "ground_truth", "processed", "exports", "reports")
ENGINE_READABLE = ("master", "inbox")
EVALUATION_ONLY = ("source", "ground_truth")
