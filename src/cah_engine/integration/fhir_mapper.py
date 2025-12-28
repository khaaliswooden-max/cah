"""
FHIR R4 Mapper

Transform normalized data to FHIR R4 resources for interoperability.
Supports USCDI v3 compliance.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Optional
from uuid import uuid4

from cah_engine.core.models import (
    ClinicalEncounter,
    CostReportMetrics,
    Claim,
    FacilitySnapshot,
)
from cah_engine.core.enums import EncounterType, DispositionCode


@dataclass
class FHIRResource:
    """Base class for FHIR resources."""
    
    resource_type: str
    id: str = ""
    meta: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())
        if not self.meta:
            self.meta = {
                "lastUpdated": datetime.now().isoformat(),
                "profile": [],
            }
    
    def to_dict(self) -> dict:
        """Convert to FHIR JSON representation."""
        return {
            "resourceType": self.resource_type,
            "id": self.id,
            "meta": self.meta,
        }


@dataclass
class FHIRBundle:
    """FHIR Bundle containing multiple resources."""
    
    bundle_type: str = "collection"
    entries: list[FHIRResource] = field(default_factory=list)
    total: int = 0
    
    def __post_init__(self):
        if self.total == 0:
            self.total = len(self.entries)
    
    def add(self, resource: FHIRResource) -> None:
        """Add a resource to the bundle."""
        self.entries.append(resource)
        self.total = len(self.entries)
    
    def to_dict(self) -> dict:
        """Convert to FHIR JSON representation."""
        return {
            "resourceType": "Bundle",
            "type": self.bundle_type,
            "total": self.total,
            "entry": [
                {"resource": entry.to_dict()}
                for entry in self.entries
            ],
        }


class ResourceMapper(ABC):
    """Abstract base class for FHIR resource mappers."""
    
    @abstractmethod
    def map(self, source: Any) -> FHIRResource:
        """Map source data to a FHIR resource."""
        pass
    
    @abstractmethod
    def validate(self, resource: FHIRResource) -> list[str]:
        """Validate a FHIR resource. Returns list of validation errors."""
        pass


class EncounterMapper(ResourceMapper):
    """
    Map clinical encounters to FHIR Encounter resources.
    
    Profile: http://hl7.org/fhir/us/core/StructureDefinition/us-core-encounter
    """
    
    PROFILE = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-encounter"
    
    # Encounter class code mappings
    CLASS_CODES = {
        EncounterType.INPATIENT: {"code": "IMP", "display": "inpatient encounter"},
        EncounterType.EMERGENCY: {"code": "EMER", "display": "emergency"},
        EncounterType.OUTPATIENT: {"code": "AMB", "display": "ambulatory"},
        EncounterType.OBSERVATION: {"code": "OBSENC", "display": "observation encounter"},
        EncounterType.SWING_BED: {"code": "SS", "display": "short stay"},
    }
    
    # Disposition code mappings
    DISPOSITION_CODES = {
        DispositionCode.HOME: {"code": "home", "display": "Home"},
        DispositionCode.HOME_HEALTH: {"code": "hosp", "display": "Home health service"},
        DispositionCode.TRANSFER_ACUTE: {"code": "other-hcf", "display": "Other healthcare facility"},
        DispositionCode.TRANSFER_SNF: {"code": "snf", "display": "Skilled nursing facility"},
        DispositionCode.TRANSFER_IRF: {"code": "rehab", "display": "Rehabilitation"},
        DispositionCode.TRANSFER_LTCH: {"code": "long", "display": "Long-term care"},
        DispositionCode.EXPIRED: {"code": "exp", "display": "Expired"},
        DispositionCode.AMA: {"code": "aadvice", "display": "Left against advice"},
        DispositionCode.HOSPICE_HOME: {"code": "hospice", "display": "Hospice"},
        DispositionCode.HOSPICE_FACILITY: {"code": "hospice", "display": "Hospice"},
        DispositionCode.OTHER: {"code": "oth", "display": "Other"},
    }
    
    def map(self, encounter: ClinicalEncounter) -> FHIRResource:
        """Map ClinicalEncounter to FHIR Encounter."""
        resource = FHIRResource(
            resource_type="Encounter",
            id=encounter.encounter_id,
            meta={
                "lastUpdated": datetime.now().isoformat(),
                "profile": [self.PROFILE],
            },
        )
        
        # Build the full resource
        fhir_data = resource.to_dict()
        
        # Status
        if encounter.discharge_datetime:
            fhir_data["status"] = "finished"
        else:
            fhir_data["status"] = "in-progress"
        
        # Class
        class_info = self.CLASS_CODES.get(
            encounter.encounter_type,
            self.CLASS_CODES[EncounterType.INPATIENT]
        )
        fhir_data["class"] = {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": class_info["code"],
            "display": class_info["display"],
        }
        
        # Type (encounter type)
        fhir_data["type"] = [{
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": self._get_snomed_code(encounter.encounter_type),
                "display": encounter.encounter_type.value,
            }],
        }]
        
        # Subject (patient reference)
        fhir_data["subject"] = {
            "reference": f"Patient/{encounter.patient_id}",
        }
        
        # Period
        fhir_data["period"] = {
            "start": encounter.admit_datetime.isoformat(),
        }
        if encounter.discharge_datetime:
            fhir_data["period"]["end"] = encounter.discharge_datetime.isoformat()
        
        # Participant (attending provider)
        if encounter.attending_provider:
            fhir_data["participant"] = [{
                "type": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                        "code": "ATND",
                        "display": "attender",
                    }],
                }],
                "individual": {
                    "reference": f"Practitioner/{encounter.attending_provider}",
                },
            }]
        
        # Hospitalization (for inpatient encounters)
        if encounter.encounter_type in (EncounterType.INPATIENT, EncounterType.OBSERVATION):
            disp_info = self.DISPOSITION_CODES.get(
                encounter.disposition,
                self.DISPOSITION_CODES[DispositionCode.OTHER]
            )
            fhir_data["hospitalization"] = {
                "dischargeDisposition": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/discharge-disposition",
                        "code": disp_info["code"],
                        "display": disp_info["display"],
                    }],
                },
            }
            
            # Admission source if available
            if encounter.admission_source:
                fhir_data["hospitalization"]["admitSource"] = {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/admit-source",
                        "code": encounter.admission_source,
                    }],
                }
        
        # Length of stay extension
        if encounter.los_hours > 0:
            fhir_data["extension"] = [{
                "url": "http://example.org/fhir/StructureDefinition/encounter-los-hours",
                "valueDecimal": round(encounter.los_hours, 2),
            }]
        
        # Store all data in the resource
        resource._data = fhir_data
        resource.to_dict = lambda: fhir_data
        
        return resource
    
    def validate(self, resource: FHIRResource) -> list[str]:
        """Validate Encounter resource against US Core profile."""
        errors = []
        data = resource.to_dict()
        
        # Required elements
        required = ["status", "class", "type", "subject"]
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Status must be valid
        valid_statuses = [
            "planned", "arrived", "triaged", "in-progress",
            "onleave", "finished", "cancelled", "entered-in-error", "unknown"
        ]
        if data.get("status") not in valid_statuses:
            errors.append(f"Invalid status: {data.get('status')}")
        
        # Class must have code
        if "class" in data and "code" not in data["class"]:
            errors.append("Encounter.class must have a code")
        
        # Subject must be a reference
        if "subject" in data and "reference" not in data["subject"]:
            errors.append("Encounter.subject must be a reference")
        
        return errors
    
    def _get_snomed_code(self, encounter_type: EncounterType) -> str:
        """Get SNOMED CT code for encounter type."""
        codes = {
            EncounterType.INPATIENT: "32485007",  # Hospital admission
            EncounterType.EMERGENCY: "4525004",   # Emergency department visit
            EncounterType.OUTPATIENT: "281036007",  # Outpatient encounter
            EncounterType.OBSERVATION: "448951000124107",  # Observation stay
            EncounterType.SWING_BED: "183452005",  # Nursing care
        }
        return codes.get(encounter_type, "308335008")


class PatientMapper(ResourceMapper):
    """
    Map patient data to FHIR Patient resources.
    
    Profile: http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient
    """
    
    PROFILE = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
    
    def map(self, patient_data: dict) -> FHIRResource:
        """Map patient dictionary to FHIR Patient."""
        resource = FHIRResource(
            resource_type="Patient",
            id=patient_data.get("patient_id", str(uuid4())),
            meta={
                "lastUpdated": datetime.now().isoformat(),
                "profile": [self.PROFILE],
            },
        )
        
        fhir_data = resource.to_dict()
        
        # Identifier
        fhir_data["identifier"] = [{
            "system": patient_data.get("identifier_system", "urn:oid:2.16.840.1.113883.4.1"),
            "value": patient_data.get("patient_id", ""),
        }]
        
        # Name
        if patient_data.get("name"):
            name_parts = patient_data["name"].split()
            fhir_data["name"] = [{
                "use": "official",
                "family": name_parts[-1] if name_parts else "Unknown",
                "given": name_parts[:-1] if len(name_parts) > 1 else ["Unknown"],
            }]
        else:
            fhir_data["name"] = [{
                "use": "official",
                "family": "De-identified",
                "given": ["Patient"],
            }]
        
        # Gender
        gender = patient_data.get("gender", "unknown")
        fhir_data["gender"] = gender.lower() if gender in ["male", "female", "other"] else "unknown"
        
        # Birth date
        if patient_data.get("birth_date"):
            bd = patient_data["birth_date"]
            if isinstance(bd, date):
                fhir_data["birthDate"] = bd.isoformat()
            else:
                fhir_data["birthDate"] = str(bd)
        
        # Address
        if patient_data.get("address"):
            fhir_data["address"] = [{
                "use": "home",
                "line": [patient_data.get("address", "")],
                "city": patient_data.get("city", ""),
                "state": patient_data.get("state", ""),
                "postalCode": patient_data.get("zip_code", ""),
            }]
        
        resource._data = fhir_data
        resource.to_dict = lambda: fhir_data
        
        return resource
    
    def validate(self, resource: FHIRResource) -> list[str]:
        """Validate Patient resource against US Core profile."""
        errors = []
        data = resource.to_dict()
        
        # Required: identifier, name, gender
        if not data.get("identifier"):
            errors.append("Missing required field: identifier")
        
        if not data.get("name"):
            errors.append("Missing required field: name")
        
        if not data.get("gender"):
            errors.append("Missing required field: gender")
        elif data["gender"] not in ["male", "female", "other", "unknown"]:
            errors.append(f"Invalid gender: {data['gender']}")
        
        return errors


class ConditionMapper(ResourceMapper):
    """
    Map diagnosis codes to FHIR Condition resources.
    
    Profile: http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition
    """
    
    PROFILE = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition"
    
    def map(self, diagnosis_data: dict) -> FHIRResource:
        """Map diagnosis to FHIR Condition."""
        resource = FHIRResource(
            resource_type="Condition",
            id=diagnosis_data.get("condition_id", str(uuid4())),
            meta={
                "lastUpdated": datetime.now().isoformat(),
                "profile": [self.PROFILE],
            },
        )
        
        fhir_data = resource.to_dict()
        
        # Category (problem-list-item or encounter-diagnosis)
        category = diagnosis_data.get("category", "encounter-diagnosis")
        fhir_data["category"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                "code": category,
            }],
        }]
        
        # Code (diagnosis)
        icd_code = diagnosis_data.get("code", "")
        fhir_data["code"] = {
            "coding": [{
                "system": "http://hl7.org/fhir/sid/icd-10-cm",
                "code": icd_code,
                "display": diagnosis_data.get("display", ""),
            }],
        }
        
        # Clinical status
        fhir_data["clinicalStatus"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": diagnosis_data.get("clinical_status", "active"),
            }],
        }
        
        # Verification status
        fhir_data["verificationStatus"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": diagnosis_data.get("verification_status", "confirmed"),
            }],
        }
        
        # Subject
        fhir_data["subject"] = {
            "reference": f"Patient/{diagnosis_data.get('patient_id', '')}",
        }
        
        # Encounter
        if diagnosis_data.get("encounter_id"):
            fhir_data["encounter"] = {
                "reference": f"Encounter/{diagnosis_data['encounter_id']}",
            }
        
        # Onset
        if diagnosis_data.get("onset_date"):
            fhir_data["onsetDateTime"] = diagnosis_data["onset_date"]
        
        resource._data = fhir_data
        resource.to_dict = lambda: fhir_data
        
        return resource
    
    def validate(self, resource: FHIRResource) -> list[str]:
        """Validate Condition resource."""
        errors = []
        data = resource.to_dict()
        
        if not data.get("category"):
            errors.append("Missing required field: category")
        
        if not data.get("code"):
            errors.append("Missing required field: code")
        
        if not data.get("subject"):
            errors.append("Missing required field: subject")
        
        return errors


class ClaimMapper(ResourceMapper):
    """Map claims to FHIR Claim resources."""
    
    def map(self, claim: Claim) -> FHIRResource:
        """Map Claim to FHIR Claim resource."""
        resource = FHIRResource(
            resource_type="Claim",
            id=claim.claim_id,
            meta={
                "lastUpdated": datetime.now().isoformat(),
            },
        )
        
        fhir_data = resource.to_dict()
        
        # Status
        status_map = {
            "draft": "draft",
            "ready": "active",
            "submitted": "active",
            "accepted": "active",
            "paid": "active",
            "denied": "cancelled",
        }
        fhir_data["status"] = status_map.get(claim.status.value, "active")
        
        # Type
        claim_type = "institutional" if claim.claim_type == "837I" else "professional"
        fhir_data["type"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                "code": claim_type,
            }],
        }
        
        # Use
        fhir_data["use"] = "claim"
        
        # Patient
        fhir_data["patient"] = {
            "reference": f"Patient/{claim.patient_id}",
        }
        
        # Created
        fhir_data["created"] = claim.service_date.isoformat()
        
        # Insurer
        fhir_data["insurer"] = {
            "reference": f"Organization/{claim.payer_id}",
        }
        
        # Provider
        fhir_data["provider"] = {
            "reference": "Organization/facility",
        }
        
        # Priority
        fhir_data["priority"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/processpriority",
                "code": "normal",
            }],
        }
        
        # Total
        fhir_data["total"] = {
            "value": float(claim.total_charges),
            "currency": "USD",
        }
        
        # Diagnosis
        if claim.diagnosis_codes:
            fhir_data["diagnosis"] = [
                {
                    "sequence": i + 1,
                    "diagnosisCodeableConcept": {
                        "coding": [{
                            "system": "http://hl7.org/fhir/sid/icd-10-cm",
                            "code": code,
                        }],
                    },
                }
                for i, code in enumerate(claim.diagnosis_codes)
            ]
        
        # Procedure
        if claim.procedure_codes:
            fhir_data["procedure"] = [
                {
                    "sequence": i + 1,
                    "procedureCodeableConcept": {
                        "coding": [{
                            "system": "http://www.ama-assn.org/go/cpt",
                            "code": code,
                        }],
                    },
                }
                for i, code in enumerate(claim.procedure_codes)
            ]
        
        resource._data = fhir_data
        resource.to_dict = lambda: fhir_data
        
        return resource
    
    def validate(self, resource: FHIRResource) -> list[str]:
        """Validate Claim resource."""
        errors = []
        data = resource.to_dict()
        
        required = ["status", "type", "patient", "created"]
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        return errors


class OrganizationMapper(ResourceMapper):
    """Map facility data to FHIR Organization resources."""
    
    def map(self, metrics: CostReportMetrics) -> FHIRResource:
        """Map CostReportMetrics to FHIR Organization."""
        resource = FHIRResource(
            resource_type="Organization",
            id=metrics.provider_id,
        )
        
        fhir_data = resource.to_dict()
        
        # Identifier
        fhir_data["identifier"] = [{
            "system": "http://hl7.org/fhir/sid/us-npi",
            "value": metrics.provider_id,
        }]
        
        # Type
        fhir_data["type"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                "code": "prov",
                "display": "Healthcare Provider",
            }],
        }]
        
        # Active
        fhir_data["active"] = True
        
        # Financial extensions (custom)
        fhir_data["extension"] = [
            {
                "url": "http://example.org/fhir/StructureDefinition/organization-staffed-beds",
                "valueInteger": metrics.staffed_beds,
            },
            {
                "url": "http://example.org/fhir/StructureDefinition/organization-operating-margin",
                "valueDecimal": round(metrics.operating_margin, 2),
            },
            {
                "url": "http://example.org/fhir/StructureDefinition/organization-occupancy-rate",
                "valueDecimal": round(metrics.occupancy_rate, 2),
            },
        ]
        
        resource._data = fhir_data
        resource.to_dict = lambda: fhir_data
        
        return resource
    
    def validate(self, resource: FHIRResource) -> list[str]:
        """Validate Organization resource."""
        errors = []
        data = resource.to_dict()
        
        if not data.get("identifier"):
            errors.append("Missing required field: identifier")
        
        return errors


class FHIRMapper:
    """
    Unified FHIR mapping coordinator.
    
    Provides high-level interface for transforming various data types
    to FHIR R4 resources.
    """
    
    def __init__(self):
        self.encounter_mapper = EncounterMapper()
        self.patient_mapper = PatientMapper()
        self.condition_mapper = ConditionMapper()
        self.claim_mapper = ClaimMapper()
        self.organization_mapper = OrganizationMapper()
    
    def map_encounter(self, encounter: ClinicalEncounter) -> FHIRResource:
        """Map a clinical encounter to FHIR."""
        return self.encounter_mapper.map(encounter)
    
    def map_encounters_to_bundle(
        self,
        encounters: list[ClinicalEncounter],
        include_conditions: bool = True,
    ) -> FHIRBundle:
        """Map multiple encounters to a FHIR Bundle."""
        bundle = FHIRBundle(bundle_type="collection")
        
        # Track unique patients
        patients_added = set()
        
        for encounter in encounters:
            # Add encounter
            enc_resource = self.encounter_mapper.map(encounter)
            bundle.add(enc_resource)
            
            # Add patient if not already added
            if encounter.patient_id not in patients_added:
                patient_resource = self.patient_mapper.map({
                    "patient_id": encounter.patient_id,
                })
                bundle.add(patient_resource)
                patients_added.add(encounter.patient_id)
            
            # Add conditions if requested
            if include_conditions and encounter.principal_diagnosis:
                # Principal diagnosis
                condition = self.condition_mapper.map({
                    "code": encounter.principal_diagnosis,
                    "patient_id": encounter.patient_id,
                    "encounter_id": encounter.encounter_id,
                    "category": "encounter-diagnosis",
                })
                bundle.add(condition)
                
                # Secondary diagnoses
                for dx in encounter.secondary_diagnoses:
                    condition = self.condition_mapper.map({
                        "code": dx,
                        "patient_id": encounter.patient_id,
                        "encounter_id": encounter.encounter_id,
                        "category": "encounter-diagnosis",
                    })
                    bundle.add(condition)
        
        return bundle
    
    def map_facility(self, metrics: CostReportMetrics) -> FHIRResource:
        """Map facility metrics to FHIR Organization."""
        return self.organization_mapper.map(metrics)
    
    def map_claim(self, claim: Claim) -> FHIRResource:
        """Map a claim to FHIR."""
        return self.claim_mapper.map(claim)
    
    def validate_resource(self, resource: FHIRResource) -> list[str]:
        """Validate a FHIR resource."""
        resource_type = resource.resource_type
        
        mapper_map = {
            "Encounter": self.encounter_mapper,
            "Patient": self.patient_mapper,
            "Condition": self.condition_mapper,
            "Claim": self.claim_mapper,
            "Organization": self.organization_mapper,
        }
        
        mapper = mapper_map.get(resource_type)
        if mapper:
            return mapper.validate(resource)
        
        return [f"Unknown resource type: {resource_type}"]
    
    def validate_bundle(self, bundle: FHIRBundle) -> dict[str, list[str]]:
        """Validate all resources in a bundle."""
        results = {}
        
        for entry in bundle.entries:
            errors = self.validate_resource(entry)
            if errors:
                results[entry.id] = errors
        
        return results

