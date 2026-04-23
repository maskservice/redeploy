"""Static analysis for migration specs — pre-flight checks before plan/apply."""
from __future__ import annotations

from .spec_analyzer import SpecAnalyzer, AnalysisResult, IssueSeverity
from .preflight_schema import PreflightResult, generate_preflight_schema, save_preflight_schema

__all__ = [
	"SpecAnalyzer",
	"AnalysisResult",
	"IssueSeverity",
	"PreflightResult",
	"generate_preflight_schema",
	"save_preflight_schema",
]
