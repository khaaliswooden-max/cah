"""
Module 1: Data Foundation

Extract and normalize data from existing CAH systems without requiring system modifications.
Supports batch processing with streaming capability for memory efficiency.
"""

from cah_engine.foundation.ehr_extract import (
    EHRExtractor,
    CCDAParser,
    HL7v2Parser,
)
from cah_engine.foundation.cost_report import (
    CostReportParser,
    CostReportWorksheet,
)
from cah_engine.foundation.external_data import (
    ExternalDataClient,
    HRSADataSource,
    CMSProviderSource,
)

__all__ = [
    "EHRExtractor",
    "CCDAParser",
    "HL7v2Parser",
    "CostReportParser",
    "CostReportWorksheet",
    "ExternalDataClient",
    "HRSADataSource",
    "CMSProviderSource",
]

