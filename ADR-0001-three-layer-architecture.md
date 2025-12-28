# ADR-0001: Three-Layer Inverted Architecture

## Status

Accepted

## Date

2025-12-28

## Context

Traditional healthcare IT architectures assume enterprise-scale resources: dedicated IT teams, substantial budgets, high patient volumes to amortize costs, and reliable high-bandwidth connectivity. Critical Access Hospitals (CAHs) operate under the inverse of these assumptions:

- 1-2 IT FTE (often shared with other duties)
- $10-50K annual IT budget beyond EHR maintenance
- 400-600 annual admissions (low volume)
- Rural broadband (25/3 Mbps, intermittent)

Conventional "scale down" approaches fail because they start from enterprise architectures and attempt to simplify. This preserves assumptions about connectivity, maintenance overhead, and integration complexity that are incompatible with CAH reality.

The problem: **How do we design a system architecture that is viable within MV-CAHI constraints while providing meaningful analytical capabilities?**

## Decision

We will implement a **Three-Layer Inverted Architecture** that treats data flow as the primary product rather than applications:

### Layer 1: Foundation
- Extract and normalize data from existing CAH systems
- No EHR vendor dependencies
- Batch processing (not real-time)
- Local storage first, cloud sync optional
- Runs on commodity hardware

### Layer 2: Integration
- Transform to interoperable formats (FHIR R4, X12)
- Validate against regulatory constraints
- Queue-based sync for intermittent connectivity
- Graceful degradation when offline

### Layer 3: Insight
- Generate actionable intelligence
- Tied to specific decision points
- Cached locally for offline access
- Minimal training required

The architecture inverts the traditional model by:
1. Building up from CAH constraints rather than scaling down from enterprise
2. Treating connectivity as optional rather than required
3. Minimizing maintenance burden through self-contained modules
4. Enabling incremental adoption without system-wide changes

## Consequences

### Positive

- **Offline-first**: Full Layer 1-2 functionality without connectivity
- **Low maintenance**: Self-contained modules, minimal configuration
- **Incremental adoption**: Start with one layer, add as resources allow
- **Vendor-agnostic**: No EHR integration required for basic function
- **MV-CAHI compliant**: Validated against reference constraints

### Negative

- **Not real-time**: Batch processing means latency in insights
- **Limited scope**: Cannot replace core EHR functionality
- **Learning curve**: Novel architecture requires documentation
- **Integration effort**: Initial setup requires data mapping

### Neutral

- Shifts complexity from ongoing maintenance to initial configuration
- Trades feature richness for reliability and simplicity
- Prioritizes broad applicability over specialized optimization

## Alternatives Considered

### Alternative 1: Cloud-First Architecture

Standard SaaS model with cloud processing and local thin client.

**Rejected because**: Assumes reliable connectivity (not available in rural settings), requires ongoing bandwidth costs, creates dependency on external service availability.

### Alternative 2: EHR-Embedded Modules

Build functionality as plugins/modules within existing EHR systems.

**Rejected because**: Creates vendor lock-in, requires different implementations for each EHR, depends on EHR vendor cooperation, may require costly certifications.

### Alternative 3: Hybrid Real-Time/Batch

Real-time processing when connected, batch when offline.

**Rejected because**: Complexity of dual-mode operation exceeds CAH IT capacity, inconsistent user experience, more failure modes to manage.

## Related

- [MV-CAHI.md](../MV-CAHI.md): Minimum Viable CAH Infrastructure specification
- [ARCHITECTURE.md](../ARCHITECTURE.md): Detailed architecture documentation

## Notes

This architecture is inspired by patterns from:
- Offline-first web applications
- Edge computing in low-connectivity environments
- Modular healthcare interoperability standards (FHIR)

The three-layer approach allows CAHs to adopt incrementally: start with Foundation for data extraction, add Integration for compliance, enable Insight as capacity develops.

Future ADRs will address specific technical choices within each layer.
