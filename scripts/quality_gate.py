#!/usr/bin/env python3
"""Quality gate for redeploy — runs pyqual analyze stage and checks metrics."""
import sys
from pathlib import Path

# Load pyqual pipeline to discover thresholds
import yaml
config = yaml.safe_load(Path("pyqual.yaml").read_text())
metrics_cfg = config.get("pipeline", {}).get("metrics", {})
cc_max = metrics_cfg.get("cc_max", 15)
critical_max = metrics_cfg.get("critical_max", 80)

# Run analyze stage only (avoids LLM-based validate/prefact hanging)
try:
    from pyqual.pipeline import run_pipeline
    result = run_pipeline(config, stages=["analyze"])
except ImportError:
    print("❌ pyqual not available")
    sys.exit(1)
except Exception as e:
    print(f"❌ pyqual analyze failed: {e}")
    sys.exit(1)

# Extract metrics from result
cc = getattr(result, "cc", None)
critical = getattr(result, "critical", None)

if cc is None or critical is None:
    print("⚠️  Could not extract metrics from pyqual result")
    print(result)
    sys.exit(1)

print(f"📊 cc={cc:.1f} (threshold ≤{cc_max})")
print(f"📊 critical={critical} (threshold ≤{critical_max})")

failed = False
if cc > cc_max:
    print(f"❌ FAIL: cc {cc:.1f} > {cc_max}")
    failed = True
if critical > critical_max:
    print(f"❌ FAIL: critical {critical} > {critical_max}")
    failed = True

if failed:
    sys.exit(1)

print("✅ redeploy quality gate passed")
sys.exit(0)
