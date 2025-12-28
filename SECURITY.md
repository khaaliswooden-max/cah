# Security Policy

## Overview

The CAH Transformation Engine processes models and algorithms related to healthcare operations. While this repository does not directly handle Protected Health Information (PHI), security remains paramount given the healthcare context and potential downstream applications.

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

Instead, please report vulnerabilities via email:

**Khaalis Wooden**  
kwooden@visionblox.com  
Subject: [SECURITY] CAH Transformation Engine Vulnerability Report

### What to Include

1. **Description** — Nature of the vulnerability
2. **Attack Vector** — How the vulnerability could be exploited
3. **Impact Assessment** — Potential consequences
4. **Steps to Reproduce** — Detailed reproduction steps
5. **Suggested Fix** — If you have one
6. **Your Contact Info** — For follow-up

### Response Timeline

| Phase | Timeframe |
|-------|-----------|
| Acknowledgment | 48 hours |
| Initial Assessment | 7 days |
| Status Update | Every 14 days |
| Resolution Target | 90 days (critical), 180 days (other) |

## Security Standards

### Healthcare Compliance Context

This project adheres to security principles aligned with:

- **HIPAA Security Rule** (45 CFR Part 164)
- **NIST Cybersecurity Framework**
- **NIST SP 800-66** (HIPAA Security Rule Implementation)

While the repository itself does not process PHI, all models and algorithms are designed with the assumption that implementations may be deployed in HIPAA-covered environments.

### Code Security Requirements

#### Dependency Management

```bash
# Check for known vulnerabilities
pip-audit

# Update dependencies
pip install --upgrade -r requirements.txt
```

#### Static Analysis

All code must pass:

```bash
# Linting
ruff check .

# Security scanning
bandit -r src/
```

#### Secrets Management

- **No secrets in code** — All credentials must use environment variables
- **No hardcoded PHI** — Even synthetic data must use obvious placeholders
- **No API keys** — Use `.env` files (excluded via `.gitignore`)

### Data Security

#### Test Data Requirements

Test data must:

1. Use obviously synthetic values (e.g., "Test Hospital", "Jane Doe")
2. Never resemble actual patient or facility identifiers
3. Be documented as synthetic in file headers

#### Sample Data Classification

| Data Type | Allowed in Repo | Notes |
|-----------|-----------------|-------|
| Synthetic test data | ✓ | Must be clearly marked |
| De-identified aggregate data | ✓ | With provenance documentation |
| CMS public cost reports | ✓ | Public domain |
| Individual patient data | ✗ | Never permitted |
| Facility identifiers | ✗ | Use synthetic only |

### Infrastructure Security

#### MV-CAHI Security Baseline

Models designed for Minimum Viable CAH Infrastructure must account for:

| Control | MV-CAHI Reality | Design Implication |
|---------|-----------------|-------------------|
| IT Staffing | 1-2 FTE | Minimal maintenance burden |
| Patch Cadence | Monthly at best | No zero-day dependencies |
| Network | 25/3 Mbps rural | Offline-capable designs |
| Monitoring | Basic or none | Built-in logging |

#### Threat Model

Algorithms and models must be resilient to:

1. **Data Integrity Attacks** — Corrupted input data
2. **Model Poisoning** — Adversarial training data (for ML models)
3. **Denial of Service** — Resource exhaustion on limited infrastructure
4. **Information Leakage** — Unintended data exposure in outputs

### Secure Development Practices

#### Pre-Commit Hooks

Required hooks in `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: detect-private-key
      - id: check-added-large-files
      - id: no-commit-to-branch
        args: [--branch, main]
  
  - repo: https://github.com/PyCQA/bandit
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
```

#### Code Review Security Checklist

Reviewers must verify:

- [ ] No hardcoded credentials or secrets
- [ ] No PHI or realistic patient data
- [ ] Input validation on all external data
- [ ] Error handling doesn't expose sensitive info
- [ ] Logging doesn't capture sensitive data
- [ ] Dependencies are up-to-date

## Disclosure Policy

We follow coordinated disclosure:

1. Reporter notifies us privately
2. We acknowledge and investigate
3. We develop and test a fix
4. We release the fix
5. We publicly disclose after users have time to update

Credit will be given to reporters unless anonymity is requested.

## Security-Related Documentation

| Document | Location |
|----------|----------|
| Threat Model | `docs/security/THREAT_MODEL.md` |
| Compliance Mapping | `docs/security/COMPLIANCE.md` |
| Incident Response | `docs/security/INCIDENT_RESPONSE.md` |

## Contact

**Security Contact**: kwooden@visionblox.com  
**PGP Key**: Available upon request

---

*Security is not optional when lives depend on healthcare systems.*
