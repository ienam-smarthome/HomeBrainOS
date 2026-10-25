"""Investigation V2's read-only, source-backed case-file foundation.

Deliberately not connected to the production orchestrator or write gateway.
"""
from .evidence import CaseFile, Coverage, EvidenceItem, build_case_file

__all__ = ["CaseFile", "Coverage", "EvidenceItem", "build_case_file"]
