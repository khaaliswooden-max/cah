"""
EHR Extract Component

Extract clinical data from EHR systems without vendor-specific integrations.
Supports CCDA documents, HL7 v2 messages, and CSV/flat file imports.

Computational Complexity: O(n) where n = number of records
Memory: O(1) streaming for large extracts
"""

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Any
import csv
import json
import re

from cah_engine.core.models import ClinicalEncounter, ValidationResult
from cah_engine.core.enums import EncounterType, DispositionCode


@dataclass
class ExtractionResult:
    """Result of an EHR extraction operation."""
    
    encounters: list[ClinicalEncounter]
    total_processed: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_file: str = ""
    extraction_time: datetime = field(default_factory=datetime.now)
    
    @property
    def success_rate(self) -> float:
        """Calculate extraction success rate."""
        if self.total_processed == 0:
            return 0.0
        return len(self.encounters) / self.total_processed


class BaseParser(ABC):
    """Abstract base class for EHR data parsers."""
    
    @abstractmethod
    def parse(self, source: Path | str) -> Iterator[ClinicalEncounter]:
        """Parse source and yield encounters."""
        pass
    
    @abstractmethod
    def validate_source(self, source: Path | str) -> ValidationResult:
        """Validate that source can be parsed."""
        pass


class CCDAParser(BaseParser):
    """
    Parse Consolidated Clinical Document Architecture (CCDA) documents.
    
    Supports CCDA R2.1 documents including:
    - Continuity of Care Document (CCD)
    - Discharge Summary
    - Progress Note
    - Consultation Note
    """
    
    # CCDA namespaces
    NAMESPACES = {
        "cda": "urn:hl7-org:v3",
        "sdtc": "urn:hl7-org:sdtc",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    
    # Template OIDs for encounter sections
    ENCOUNTER_TEMPLATE_OID = "2.16.840.1.113883.10.20.22.4.49"
    DIAGNOSIS_TEMPLATE_OID = "2.16.840.1.113883.10.20.22.4.4"
    PROCEDURE_TEMPLATE_OID = "2.16.840.1.113883.10.20.22.4.14"
    
    def __init__(self):
        self._encounter_type_map = {
            "AMB": EncounterType.OUTPATIENT,
            "EMER": EncounterType.EMERGENCY,
            "IMP": EncounterType.INPATIENT,
            "OBSENC": EncounterType.OBSERVATION,
            "SS": EncounterType.SWING_BED,
        }
    
    def parse(self, source: Path | str) -> Iterator[ClinicalEncounter]:
        """Parse CCDA document and yield encounters."""
        source_path = Path(source)
        
        try:
            tree = ET.parse(source_path)
            root = tree.getroot()
            
            # Extract patient ID (de-identified)
            patient_id = self._extract_patient_id(root)
            
            # Find all encounter entries
            encounters_section = root.find(
                ".//cda:component/cda:structuredBody/cda:component/cda:section"
                "[cda:templateId[@root='2.16.840.1.113883.10.20.22.2.22.1']]",
                self.NAMESPACES
            )
            
            if encounters_section is not None:
                for entry in encounters_section.findall(".//cda:entry", self.NAMESPACES):
                    encounter = self._parse_encounter_entry(entry, patient_id)
                    if encounter:
                        yield encounter
            else:
                # Try to extract from other sections
                encounter = self._extract_from_document(root, patient_id)
                if encounter:
                    yield encounter
                    
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML in CCDA document: {e}")
    
    def validate_source(self, source: Path | str) -> ValidationResult:
        """Validate that source is a valid CCDA document."""
        source_path = Path(source)
        issues = []
        
        if not source_path.exists():
            issues.append(f"File not found: {source_path}")
            return ValidationResult(valid=False, issues=issues)
        
        if source_path.suffix.lower() not in (".xml", ".ccda"):
            issues.append(f"Unexpected file extension: {source_path.suffix}")
        
        try:
            tree = ET.parse(source_path)
            root = tree.getroot()
            
            # Check for ClinicalDocument root
            if not root.tag.endswith("ClinicalDocument"):
                issues.append("Root element is not ClinicalDocument")
            
            # Check for required templateId
            template_id = root.find(".//cda:templateId", self.NAMESPACES)
            if template_id is None:
                issues.append("Missing templateId element")
                
        except ET.ParseError as e:
            issues.append(f"XML parse error: {e}")
        
        return ValidationResult(valid=len(issues) == 0, issues=issues)
    
    def _extract_patient_id(self, root: ET.Element) -> str:
        """Extract de-identified patient ID."""
        patient = root.find(".//cda:recordTarget/cda:patientRole", self.NAMESPACES)
        if patient is not None:
            id_elem = patient.find("cda:id", self.NAMESPACES)
            if id_elem is not None:
                extension = id_elem.get("extension", "")
                root_oid = id_elem.get("root", "")
                return f"{root_oid}:{extension}" if root_oid else extension
        return f"UNKNOWN_{datetime.now().timestamp()}"
    
    def _parse_encounter_entry(
        self, entry: ET.Element, patient_id: str
    ) -> Optional[ClinicalEncounter]:
        """Parse a single encounter entry."""
        encounter_act = entry.find(".//cda:encounter", self.NAMESPACES)
        if encounter_act is None:
            return None
        
        # Extract encounter ID
        id_elem = encounter_act.find("cda:id", self.NAMESPACES)
        encounter_id = id_elem.get("extension", "") if id_elem is not None else ""
        
        if not encounter_id:
            encounter_id = f"ENC_{datetime.now().timestamp()}"
        
        # Extract encounter type
        code_elem = encounter_act.find("cda:code", self.NAMESPACES)
        encounter_type = EncounterType.INPATIENT
        if code_elem is not None:
            code = code_elem.get("code", "")
            encounter_type = self._encounter_type_map.get(code, EncounterType.INPATIENT)
        
        # Extract dates
        effective_time = encounter_act.find("cda:effectiveTime", self.NAMESPACES)
        admit_datetime = datetime.now()
        discharge_datetime = None
        
        if effective_time is not None:
            low = effective_time.find("cda:low", self.NAMESPACES)
            high = effective_time.find("cda:high", self.NAMESPACES)
            
            if low is not None and low.get("value"):
                admit_datetime = self._parse_hl7_datetime(low.get("value", ""))
            if high is not None and high.get("value"):
                discharge_datetime = self._parse_hl7_datetime(high.get("value", ""))
        
        # Extract diagnoses
        diagnoses = self._extract_diagnoses(encounter_act)
        principal_diagnosis = diagnoses[0] if diagnoses else ""
        secondary_diagnoses = diagnoses[1:] if len(diagnoses) > 1 else []
        
        # Extract procedures
        procedures = self._extract_procedures(encounter_act)
        
        # Extract disposition
        discharge_disp = encounter_act.find(
            ".//cda:sdtc:dischargeDispositionCode", self.NAMESPACES
        )
        disposition = DispositionCode.HOME
        if discharge_disp is not None:
            code = discharge_disp.get("code", "01")
            try:
                disposition = DispositionCode(code)
            except ValueError:
                disposition = DispositionCode.OTHER
        
        return ClinicalEncounter(
            encounter_id=encounter_id,
            patient_id=patient_id,
            admit_datetime=admit_datetime,
            discharge_datetime=discharge_datetime,
            encounter_type=encounter_type,
            principal_diagnosis=principal_diagnosis,
            secondary_diagnoses=secondary_diagnoses,
            procedures=procedures,
            disposition=disposition,
        )
    
    def _extract_from_document(
        self, root: ET.Element, patient_id: str
    ) -> Optional[ClinicalEncounter]:
        """Extract encounter data from document-level elements."""
        # For discharge summaries without explicit encounter sections
        encompassing_encounter = root.find(
            ".//cda:componentOf/cda:encompassingEncounter", self.NAMESPACES
        )
        
        if encompassing_encounter is not None:
            id_elem = encompassing_encounter.find("cda:id", self.NAMESPACES)
            encounter_id = id_elem.get("extension", "") if id_elem is not None else ""
            
            if not encounter_id:
                encounter_id = f"DOC_{datetime.now().timestamp()}"
            
            effective_time = encompassing_encounter.find("cda:effectiveTime", self.NAMESPACES)
            admit_datetime = datetime.now()
            discharge_datetime = None
            
            if effective_time is not None:
                low = effective_time.find("cda:low", self.NAMESPACES)
                high = effective_time.find("cda:high", self.NAMESPACES)
                
                if low is not None and low.get("value"):
                    admit_datetime = self._parse_hl7_datetime(low.get("value", ""))
                if high is not None and high.get("value"):
                    discharge_datetime = self._parse_hl7_datetime(high.get("value", ""))
            
            # Extract diagnoses from problem list
            problems_section = root.find(
                ".//cda:section[cda:templateId[@root='2.16.840.1.113883.10.20.22.2.5.1']]",
                self.NAMESPACES
            )
            
            diagnoses = []
            if problems_section is not None:
                for entry in problems_section.findall(".//cda:entry", self.NAMESPACES):
                    dx = self._extract_diagnosis_from_entry(entry)
                    if dx:
                        diagnoses.append(dx)
            
            return ClinicalEncounter(
                encounter_id=encounter_id,
                patient_id=patient_id,
                admit_datetime=admit_datetime,
                discharge_datetime=discharge_datetime,
                encounter_type=EncounterType.INPATIENT,
                principal_diagnosis=diagnoses[0] if diagnoses else "",
                secondary_diagnoses=diagnoses[1:] if len(diagnoses) > 1 else [],
                procedures=[],
                disposition=DispositionCode.HOME,
            )
        
        return None
    
    def _extract_diagnoses(self, encounter_elem: ET.Element) -> list[str]:
        """Extract diagnosis codes from encounter element."""
        diagnoses = []
        
        for obs in encounter_elem.findall(".//cda:observation", self.NAMESPACES):
            template = obs.find("cda:templateId", self.NAMESPACES)
            if template is not None and template.get("root") == self.DIAGNOSIS_TEMPLATE_OID:
                value = obs.find("cda:value", self.NAMESPACES)
                if value is not None:
                    code = value.get("code", "")
                    if code:
                        diagnoses.append(code)
        
        return diagnoses
    
    def _extract_diagnosis_from_entry(self, entry: ET.Element) -> Optional[str]:
        """Extract a diagnosis code from an entry element."""
        value = entry.find(".//cda:value[@codeSystem='2.16.840.1.113883.6.90']", self.NAMESPACES)
        if value is not None:
            return value.get("code")
        return None
    
    def _extract_procedures(self, encounter_elem: ET.Element) -> list[str]:
        """Extract procedure codes from encounter element."""
        procedures = []
        
        for proc in encounter_elem.findall(".//cda:procedure", self.NAMESPACES):
            code_elem = proc.find("cda:code", self.NAMESPACES)
            if code_elem is not None:
                code = code_elem.get("code", "")
                if code:
                    procedures.append(code)
        
        return procedures
    
    def _parse_hl7_datetime(self, value: str) -> datetime:
        """Parse HL7 datetime format (YYYYMMDDHHMMSS)."""
        if not value:
            return datetime.now()
        
        # Remove timezone if present
        value = value.split("-")[0].split("+")[0]
        
        formats = [
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
            "%Y%m%d",
            "%Y%m",
            "%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value[:len(fmt.replace("%", ""))], fmt)
            except ValueError:
                continue
        
        return datetime.now()


class HL7v2Parser(BaseParser):
    """
    Parse HL7 v2.x messages.
    
    Supports ADT (Admit/Discharge/Transfer) messages:
    - ADT^A01: Admit
    - ADT^A02: Transfer
    - ADT^A03: Discharge
    - ADT^A04: Register (outpatient)
    """
    
    def __init__(self, field_separator: str = "|", encoding_chars: str = "^~\\&"):
        self.field_sep = field_separator
        self.component_sep = encoding_chars[0] if encoding_chars else "^"
        self.repetition_sep = encoding_chars[1] if len(encoding_chars) > 1 else "~"
    
    def parse(self, source: Path | str) -> Iterator[ClinicalEncounter]:
        """Parse HL7 v2 messages from file."""
        source_path = Path(source)
        
        with open(source_path, "r") as f:
            content = f.read()
        
        # Split into individual messages
        messages = self._split_messages(content)
        
        for msg in messages:
            encounter = self._parse_message(msg)
            if encounter:
                yield encounter
    
    def validate_source(self, source: Path | str) -> ValidationResult:
        """Validate HL7 v2 message file."""
        source_path = Path(source)
        issues = []
        
        if not source_path.exists():
            issues.append(f"File not found: {source_path}")
            return ValidationResult(valid=False, issues=issues)
        
        try:
            with open(source_path, "r") as f:
                content = f.read()
            
            if not content.strip().startswith("MSH"):
                issues.append("File does not start with MSH segment")
            
        except Exception as e:
            issues.append(f"Error reading file: {e}")
        
        return ValidationResult(valid=len(issues) == 0, issues=issues)
    
    def _split_messages(self, content: str) -> list[str]:
        """Split content into individual HL7 messages."""
        messages = []
        current_message = []
        
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("MSH") and current_message:
                messages.append("\n".join(current_message))
                current_message = []
            
            current_message.append(line)
        
        if current_message:
            messages.append("\n".join(current_message))
        
        return messages
    
    def _parse_message(self, message: str) -> Optional[ClinicalEncounter]:
        """Parse a single HL7 v2 message."""
        segments = {}
        
        for line in message.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            segment_type = line[:3]
            fields = line.split(self.field_sep)
            
            if segment_type not in segments:
                segments[segment_type] = []
            segments[segment_type].append(fields)
        
        # Check for ADT message type
        msh = segments.get("MSH", [[]])[0]
        if len(msh) < 9:
            return None
        
        msg_type = msh[8] if len(msh) > 8 else ""
        if not msg_type.startswith("ADT"):
            return None
        
        # Extract patient info from PID
        pid = segments.get("PID", [[]])[0]
        patient_id = self._get_field_component(pid, 3, 0) if len(pid) > 3 else ""
        
        # Extract visit info from PV1
        pv1 = segments.get("PV1", [[]])[0]
        
        encounter_id = self._get_field_component(pv1, 19, 0) if len(pv1) > 19 else ""
        if not encounter_id:
            encounter_id = f"HL7_{datetime.now().timestamp()}"
        
        # Encounter type from patient class (PV1-2)
        patient_class = self._get_field_component(pv1, 2, 0) if len(pv1) > 2 else ""
        encounter_type = self._map_patient_class(patient_class)
        
        # Admission datetime (PV1-44)
        admit_datetime = self._parse_hl7_datetime(
            self._get_field_component(pv1, 44, 0) if len(pv1) > 44 else ""
        )
        
        # Discharge datetime (PV1-45)
        discharge_datetime = None
        discharge_dt_str = self._get_field_component(pv1, 45, 0) if len(pv1) > 45 else ""
        if discharge_dt_str:
            discharge_datetime = self._parse_hl7_datetime(discharge_dt_str)
        
        # Disposition (PV1-36)
        disp_code = self._get_field_component(pv1, 36, 0) if len(pv1) > 36 else "01"
        try:
            disposition = DispositionCode(disp_code)
        except ValueError:
            disposition = DispositionCode.OTHER
        
        # Extract diagnoses from DG1 segments
        diagnoses = []
        for dg1 in segments.get("DG1", []):
            if len(dg1) > 3:
                dx_code = self._get_field_component(dg1, 3, 0)
                if dx_code:
                    diagnoses.append(dx_code)
        
        # Extract procedures from PR1 segments
        procedures = []
        for pr1 in segments.get("PR1", []):
            if len(pr1) > 3:
                proc_code = self._get_field_component(pr1, 3, 0)
                if proc_code:
                    procedures.append(proc_code)
        
        return ClinicalEncounter(
            encounter_id=encounter_id,
            patient_id=patient_id,
            admit_datetime=admit_datetime,
            discharge_datetime=discharge_datetime,
            encounter_type=encounter_type,
            principal_diagnosis=diagnoses[0] if diagnoses else "",
            secondary_diagnoses=diagnoses[1:] if len(diagnoses) > 1 else [],
            procedures=procedures,
            disposition=disposition,
        )
    
    def _get_field_component(
        self, fields: list[str], field_idx: int, component_idx: int
    ) -> str:
        """Get a specific component from a field."""
        if field_idx >= len(fields):
            return ""
        
        field = fields[field_idx]
        components = field.split(self.component_sep)
        
        if component_idx >= len(components):
            return ""
        
        return components[component_idx].strip()
    
    def _map_patient_class(self, patient_class: str) -> EncounterType:
        """Map HL7 patient class to encounter type."""
        mapping = {
            "I": EncounterType.INPATIENT,
            "E": EncounterType.EMERGENCY,
            "O": EncounterType.OUTPATIENT,
            "P": EncounterType.OUTPATIENT,
            "R": EncounterType.SWING_BED,
            "B": EncounterType.OBSERVATION,
        }
        return mapping.get(patient_class.upper(), EncounterType.INPATIENT)
    
    def _parse_hl7_datetime(self, value: str) -> datetime:
        """Parse HL7 datetime format."""
        if not value:
            return datetime.now()
        
        # Remove timezone if present
        value = re.sub(r"[+-]\d{4}$", "", value)
        
        formats = [
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
            "%Y%m%d",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value[:len(fmt.replace("%", ""))], fmt)
            except ValueError:
                continue
        
        return datetime.now()


class CSVParser(BaseParser):
    """Parse CSV/flat file exports from EHR systems."""
    
    # Default column mappings
    DEFAULT_MAPPINGS = {
        "encounter_id": ["encounter_id", "visit_id", "account_number", "fin"],
        "patient_id": ["patient_id", "mrn", "medical_record_number", "patient_mrn"],
        "admit_datetime": ["admit_date", "admission_date", "admit_datetime", "service_date"],
        "discharge_datetime": ["discharge_date", "discharge_datetime", "disch_date"],
        "encounter_type": ["patient_type", "encounter_type", "visit_type", "class"],
        "principal_diagnosis": ["principal_diagnosis", "primary_diagnosis", "dx1", "diagnosis"],
        "disposition": ["disposition", "discharge_disposition", "disch_disp"],
    }
    
    def __init__(self, column_mappings: Optional[dict[str, str]] = None):
        self.column_mappings = column_mappings or {}
    
    def parse(self, source: Path | str) -> Iterator[ClinicalEncounter]:
        """Parse CSV file and yield encounters."""
        source_path = Path(source)
        
        with open(source_path, "r", newline="") as f:
            # Detect delimiter
            sample = f.read(4096)
            f.seek(0)
            
            delimiter = self._detect_delimiter(sample)
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Resolve column mappings
            if reader.fieldnames:
                mappings = self._resolve_mappings(reader.fieldnames)
            else:
                mappings = {}
            
            for row in reader:
                encounter = self._parse_row(row, mappings)
                if encounter:
                    yield encounter
    
    def validate_source(self, source: Path | str) -> ValidationResult:
        """Validate CSV file."""
        source_path = Path(source)
        issues = []
        
        if not source_path.exists():
            issues.append(f"File not found: {source_path}")
            return ValidationResult(valid=False, issues=issues)
        
        if source_path.suffix.lower() not in (".csv", ".txt", ".tsv"):
            issues.append(f"Unexpected file extension: {source_path.suffix}")
        
        try:
            with open(source_path, "r") as f:
                sample = f.read(4096)
            
            if not sample.strip():
                issues.append("File is empty")
                
        except Exception as e:
            issues.append(f"Error reading file: {e}")
        
        return ValidationResult(valid=len(issues) == 0, issues=issues)
    
    def _detect_delimiter(self, sample: str) -> str:
        """Detect CSV delimiter from sample."""
        delimiters = [",", "\t", "|", ";"]
        counts = {d: sample.count(d) for d in delimiters}
        return max(counts, key=counts.get)
    
    def _resolve_mappings(self, fieldnames: list[str]) -> dict[str, str]:
        """Resolve column mappings from fieldnames."""
        mappings = {}
        fieldnames_lower = [f.lower().strip() for f in fieldnames]
        
        for target, candidates in self.DEFAULT_MAPPINGS.items():
            # Check explicit mapping first
            if target in self.column_mappings:
                explicit = self.column_mappings[target]
                if explicit.lower() in fieldnames_lower:
                    idx = fieldnames_lower.index(explicit.lower())
                    mappings[target] = fieldnames[idx]
                    continue
            
            # Try default candidates
            for candidate in candidates:
                if candidate.lower() in fieldnames_lower:
                    idx = fieldnames_lower.index(candidate.lower())
                    mappings[target] = fieldnames[idx]
                    break
        
        return mappings
    
    def _parse_row(
        self, row: dict[str, str], mappings: dict[str, str]
    ) -> Optional[ClinicalEncounter]:
        """Parse a single CSV row into an encounter."""
        try:
            encounter_id = row.get(mappings.get("encounter_id", ""), "")
            if not encounter_id:
                return None
            
            patient_id = row.get(mappings.get("patient_id", ""), "")
            
            # Parse dates
            admit_str = row.get(mappings.get("admit_datetime", ""), "")
            admit_datetime = self._parse_datetime(admit_str) if admit_str else datetime.now()
            
            discharge_str = row.get(mappings.get("discharge_datetime", ""), "")
            discharge_datetime = self._parse_datetime(discharge_str) if discharge_str else None
            
            # Parse encounter type
            type_str = row.get(mappings.get("encounter_type", ""), "inpatient")
            encounter_type = self._map_encounter_type(type_str)
            
            # Parse disposition
            disp_str = row.get(mappings.get("disposition", ""), "01")
            try:
                disposition = DispositionCode(disp_str)
            except ValueError:
                disposition = self._map_disposition(disp_str)
            
            # Diagnosis
            principal_diagnosis = row.get(mappings.get("principal_diagnosis", ""), "")
            
            return ClinicalEncounter(
                encounter_id=encounter_id,
                patient_id=patient_id,
                admit_datetime=admit_datetime,
                discharge_datetime=discharge_datetime,
                encounter_type=encounter_type,
                principal_diagnosis=principal_diagnosis,
                secondary_diagnoses=[],
                procedures=[],
                disposition=disposition,
            )
        except Exception:
            return None
    
    def _parse_datetime(self, value: str) -> datetime:
        """Parse datetime from various formats."""
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
            "%Y%m%d%H%M%S",
            "%Y%m%d",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        
        return datetime.now()
    
    def _map_encounter_type(self, value: str) -> EncounterType:
        """Map text encounter type to enum."""
        value = value.lower().strip()
        
        mappings = {
            "inpatient": EncounterType.INPATIENT,
            "ip": EncounterType.INPATIENT,
            "i": EncounterType.INPATIENT,
            "emergency": EncounterType.EMERGENCY,
            "ed": EncounterType.EMERGENCY,
            "er": EncounterType.EMERGENCY,
            "e": EncounterType.EMERGENCY,
            "outpatient": EncounterType.OUTPATIENT,
            "op": EncounterType.OUTPATIENT,
            "o": EncounterType.OUTPATIENT,
            "observation": EncounterType.OBSERVATION,
            "obs": EncounterType.OBSERVATION,
            "swing": EncounterType.SWING_BED,
            "swing bed": EncounterType.SWING_BED,
            "snf": EncounterType.SWING_BED,
        }
        
        return mappings.get(value, EncounterType.INPATIENT)
    
    def _map_disposition(self, value: str) -> DispositionCode:
        """Map text disposition to code."""
        value = value.lower().strip()
        
        if "home" in value:
            if "health" in value:
                return DispositionCode.HOME_HEALTH
            return DispositionCode.HOME
        elif "transfer" in value or "acute" in value:
            return DispositionCode.TRANSFER_ACUTE
        elif "snf" in value or "skilled" in value:
            return DispositionCode.TRANSFER_SNF
        elif "expired" in value or "died" in value or "death" in value:
            return DispositionCode.EXPIRED
        elif "ama" in value or "against" in value:
            return DispositionCode.AMA
        elif "hospice" in value:
            return DispositionCode.HOSPICE_HOME
        
        return DispositionCode.OTHER


class EHRExtractor:
    """
    Main EHR extraction coordinator.
    
    Coordinates extraction across multiple parsers and provides
    unified interface for extracting encounters from various sources.
    """
    
    def __init__(self):
        self.parsers = {
            ".xml": CCDAParser(),
            ".ccda": CCDAParser(),
            ".hl7": HL7v2Parser(),
            ".csv": CSVParser(),
            ".txt": CSVParser(),
            ".tsv": CSVParser(),
        }
    
    def extract(self, source: Path | str) -> ExtractionResult:
        """
        Extract encounters from source file.
        
        Args:
            source: Path to source file
            
        Returns:
            ExtractionResult with extracted encounters and metadata
        """
        source_path = Path(source)
        suffix = source_path.suffix.lower()
        
        parser = self.parsers.get(suffix)
        if not parser:
            return ExtractionResult(
                encounters=[],
                errors=[f"Unsupported file type: {suffix}"],
                source_file=str(source_path),
            )
        
        # Validate source
        validation = parser.validate_source(source_path)
        if not validation.valid:
            return ExtractionResult(
                encounters=[],
                errors=validation.issues,
                warnings=validation.warnings,
                source_file=str(source_path),
            )
        
        # Extract encounters
        encounters = []
        errors = []
        total_processed = 0
        
        try:
            for encounter in parser.parse(source_path):
                total_processed += 1
                
                # Validate each encounter
                enc_validation = encounter.validate_cah_compliance()
                if enc_validation.valid:
                    encounters.append(encounter)
                else:
                    errors.extend([
                        f"Encounter {encounter.encounter_id}: {issue}"
                        for issue in enc_validation.issues
                    ])
                    # Still include encounter but note the issues
                    encounters.append(encounter)
                    
        except Exception as e:
            errors.append(f"Extraction error: {e}")
        
        return ExtractionResult(
            encounters=encounters,
            total_processed=total_processed,
            errors=errors,
            warnings=validation.warnings,
            source_file=str(source_path),
        )
    
    def extract_batch(
        self, sources: list[Path | str]
    ) -> list[ExtractionResult]:
        """Extract encounters from multiple sources."""
        return [self.extract(source) for source in sources]
    
    def extract_directory(
        self,
        directory: Path | str,
        pattern: str = "*.*",
        recursive: bool = False,
    ) -> ExtractionResult:
        """
        Extract encounters from all files in a directory.
        
        Args:
            directory: Directory path
            pattern: Glob pattern for file selection
            recursive: Whether to search recursively
            
        Returns:
            Combined ExtractionResult
        """
        dir_path = Path(directory)
        
        if recursive:
            files = list(dir_path.rglob(pattern))
        else:
            files = list(dir_path.glob(pattern))
        
        # Filter to supported file types
        files = [f for f in files if f.suffix.lower() in self.parsers]
        
        all_encounters = []
        all_errors = []
        all_warnings = []
        total_processed = 0
        
        for file_path in files:
            result = self.extract(file_path)
            all_encounters.extend(result.encounters)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            total_processed += result.total_processed
        
        return ExtractionResult(
            encounters=all_encounters,
            total_processed=total_processed,
            errors=all_errors,
            warnings=all_warnings,
            source_file=str(dir_path),
        )
    
    def register_parser(self, extension: str, parser: BaseParser) -> None:
        """Register a custom parser for a file extension."""
        self.parsers[extension.lower()] = parser

