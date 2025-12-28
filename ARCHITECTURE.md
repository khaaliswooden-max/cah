# System Architecture

## Overview

The CAH Transformation Engine implements a **three-layer architecture** designed to invert conventional enterprise approaches for resource-constrained rural healthcare environments. Rather than scaling down enterprise solutions, this architecture builds up from CAH constraints as first principles.

## Design Philosophy

### The Inversion Principle

Traditional healthcare IT assumes:
- High patient volumes → amortize fixed costs
- Substantial IT budgets → deploy complex systems
- Dedicated technical staff → maintain integrations
- Urban broadband → real-time cloud connectivity

CAH reality inverts each assumption:
- Low volumes → every patient encounter is high-value
- Minimal IT budget → solutions must be near-zero marginal cost
- Shared IT resources → systems must be self-maintaining
- Rural connectivity → offline-first design

**Our architecture treats data flow as the primary product**, enabling modular solutions that scale down rather than up.

---

## Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LAYER 3: INSIGHT                              │
│                                                                         │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                  │
│   │  Decision   │   │  Predictive │   │  Performance│                  │
│   │  Support    │   │  Analytics  │   │  Dashboards │                  │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                  │
│          │                 │                 │                          │
├──────────┴─────────────────┴─────────────────┴──────────────────────────┤
│                           LAYER 2: INTEGRATION                          │
│                                                                         │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                  │
│   │    FHIR     │   │   Claims    │   │  Regulatory │                  │
│   │  Adapter    │   │  Processor  │   │  Compliance │                  │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                  │
│          │                 │                 │                          │
├──────────┴─────────────────┴─────────────────┴──────────────────────────┤
│                           LAYER 1: FOUNDATION                           │
│                                                                         │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                  │
│   │    EHR      │   │   Claims    │   │    Cost     │                  │
│   │   Extract   │   │    Data     │   │   Reports   │                  │
│   └─────────────┘   └─────────────┘   └─────────────┘                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Layer 1: Foundation

**Purpose**: Extract and normalize data from existing CAH systems without requiring system modifications.

| Component | Input | Output | Complexity |
|-----------|-------|--------|------------|
| EHR Extract | Native EHR exports | Standardized records | O(n) |
| Claims Data | 837/835 files | Claim entities | O(n) |
| Cost Reports | CMS 2552-10 | Financial metrics | O(1) per report |

**Design Constraints**:
- No EHR vendor dependencies
- Batch processing (not real-time)
- Local storage first, cloud sync optional
- Runs on commodity hardware

### Layer 2: Integration

**Purpose**: Transform raw data into interoperable formats and validate against regulatory requirements.

| Component | Function | Standard |
|-----------|----------|----------|
| FHIR Adapter | Clinical data transformation | FHIR R4 / USCDI v3 |
| Claims Processor | Revenue cycle normalization | X12 5010 |
| Regulatory Compliance | Constraint validation | 42 CFR § 485.610 |

**Integration Points**:

```
EHR Data ──────────► FHIR Resources ──────────► FHIR Server
                            │
Claims Data ───────► Claim Entities ──────────► Analytics DB
                            │
Cost Reports ──────► Financial Metrics ───────► Dashboard
                            │
                            ▼
                    Compliance Engine
                            │
                            ▼
                    Regulatory Alerts
```

### Layer 3: Insight

**Purpose**: Generate actionable intelligence tied to specific CAH decisions and workflows.

| Component | Decision Support |
|-----------|-----------------|
| Decision Support | Real-time clinical and operational guidance |
| Predictive Analytics | Forecasting and risk stratification |
| Performance Dashboards | KPI monitoring and trend analysis |

**Output Requirements**:
- Tied to specific decision points (e.g., "admit vs. transfer")
- Validated against CAH-realistic data volumes
- Graceful degradation when data is incomplete

---

## Data Flow

### Nominal Flow

```
                     ┌──────────────────┐
                     │   CAH Systems    │
                     │  (EHR, Billing)  │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  Batch Extract   │
                     │   (nightly)      │
                     └────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌────────────┐  ┌────────────┐  ┌────────────┐
       │  Clinical  │  │  Financial │  │ Operational│
       │    Data    │  │    Data    │  │    Data    │
       └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
             │               │               │
             └───────────────┼───────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Integration     │
                    │  (FHIR, X12)     │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Analytics       │
                    │  Engine          │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌────────────┐ ┌────────────┐ ┌────────────┐
       │ Dashboards │ │   Alerts   │ │  Reports   │
       └────────────┘ └────────────┘ └────────────┘
```

### Offline Mode

When connectivity is unavailable (common in rural settings):

1. **Local Processing** — All Layer 1 and Layer 2 operations continue
2. **Queue Sync** — Data queued for upload when connectivity returns
3. **Cached Intelligence** — Layer 3 operates on most recent synced models
4. **Graceful Degradation** — Predictions flagged with staleness indicators

---

## Component Specifications

### EHR Extract Module

```python
class EHRExtractor:
    """
    Extract clinical data from EHR systems without vendor-specific integrations.
    
    Supported Methods:
        - CCDA document parsing
        - HL7 v2 message processing
        - CSV/flat file import
        - Manual entry interface
    
    Output: FHIR R4 Bundle
    Complexity: O(n) where n = number of records
    Memory: O(1) streaming for large extracts
    """
```

### FHIR Adapter

**Supported Resources**:

| Resource | USCDI v3 Mapping | CAH Relevance |
|----------|-----------------|---------------|
| Patient | Demographics | Census tracking |
| Encounter | Visits | LOS monitoring |
| Condition | Problems | Case mix index |
| Procedure | Interventions | Service analysis |
| Claim | Billing | Revenue cycle |
| Organization | Facility | Reporting |

### Regulatory Compliance Engine

**Constraint Validation**:

```python
@dataclass
class CAHConstraints:
    max_beds: int = 25                    # 42 CFR § 485.610(a)
    max_los_hours: int = 96               # 42 CFR § 485.610(b)
    min_distance_miles: float = 35        # 42 CFR § 485.610(c)
    emergency_service: bool = True        # 42 CFR § 485.618
    
    def validate(self, facility_data: FacilityData) -> ValidationResult:
        """Check facility data against CAH regulatory constraints."""
```

---

## Deployment Architecture

### Minimal Deployment (MV-CAHI Compliant)

```
┌─────────────────────────────────────────────────┐
│              CAH On-Premise                     │
│                                                 │
│  ┌─────────────┐     ┌─────────────────────┐   │
│  │    EHR      │────▶│  Transformation     │   │
│  │   Server    │     │  Engine             │   │
│  └─────────────┘     │  (Docker Container) │   │
│                      └──────────┬──────────┘   │
│                                 │              │
│                      ┌──────────▼──────────┐   │
│                      │  Local SQLite DB    │   │
│                      └─────────────────────┘   │
│                                                 │
└─────────────────────────────────────────────────┘
           │
           │ (Optional, when connected)
           ▼
┌─────────────────────────────────────────────────┐
│              Cloud Sync                         │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  Aggregated Analytics (No PHI)          │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Infrastructure Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Storage | 50 GB | 200 GB |
| Network | 25/3 Mbps | 100/20 Mbps |
| OS | Linux (any) | Ubuntu 22.04 LTS |

---

## Security Architecture

### Data Classification

| Layer | Data Type | Classification | Handling |
|-------|-----------|---------------|----------|
| 1 | PHI | Confidential | Encrypted at rest, no cloud sync |
| 2 | De-identified | Internal | Encrypted, optional cloud sync |
| 3 | Aggregated | Public-ready | Standard protection |

### Access Control

```
┌─────────────────────────────────────────────────────────┐
│                   Access Control Matrix                 │
├─────────────────────────────────────────────────────────┤
│  Role          │  Layer 1  │  Layer 2  │  Layer 3      │
├─────────────────────────────────────────────────────────┤
│  IT Admin      │  Config   │  Config   │  Full         │
│  Clinical      │  None     │  Read     │  Full         │
│  Financial     │  None     │  Read     │  Full         │
│  Executive     │  None     │  None     │  Dashboards   │
│  External      │  None     │  None     │  None         │
└─────────────────────────────────────────────────────────┘
```

---

## Extension Points

### Adding New Data Sources

1. Implement `DataExtractor` interface
2. Register with `ExtractorRegistry`
3. Map to FHIR resources
4. Add validation rules

### Adding New Analytics

1. Define input FHIR resources
2. Implement `AnalyticsModule` interface
3. Specify computational complexity
4. Document failure modes
5. Validate against MV-CAHI constraints

---

## Related Documents

- [METHODOLOGY.md](METHODOLOGY.md) — Research protocols
- [MV-CAHI.md](MV-CAHI.md) — Reference infrastructure specification
- [GLOSSARY.md](GLOSSARY.md) — Terminology reference

---

*Architecture designed for the constraints that matter.*
