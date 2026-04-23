"""Static analysis for migration specs — pre-flight checks before plan/apply."""
from __future__ import annotations

from .spec_analyzer import SpecAnalyzer, AnalysisResult, IssueSeverity

__all__ = ["SpecAnalyzer", "AnalysisResult", "IssueSeverity"]
