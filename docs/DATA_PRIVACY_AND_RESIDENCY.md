# Data Protection, Cryptographic Governance & Residency Architecture

**Standard**: India Digital Personal Data Protection Act (DPDPA 2023) & HIPAA Privacy Rule  
**Document Ref**: SEC-GOV-001  
**Classification**: Engineering Specification & Compliance Assurance

---

## 1. Data Residency & Processing Locations

To strictly comply with Section 9 & Cross-Border Transfer mandates of the **Digital Personal Data Protection Act 2023 (DPDPA)**, all customer personal identifiers, audio buffers, telemetry, and call databases are confined to domestic sovereign boundaries.

| Architecture Component | Provider & Infrastructure | Sovereign Location | Geographic Region / Cluster | Compliance Standard |
| :--- | :--- | :--- | :--- | :--- |
| **Telephony Gateway** | Exotel Telecom Cloud | India | Mumbai Datacenter (`@api.in.exotel.com`) | TRAI / DOT Telecom Licensing |
| **Primary Backend Compute** | AWS / Private VPC | India | Mumbai (`ap-south-1`) | DPDPA Data Processor |
| **Relational Database** | PostgreSQL + KMS | India | Mumbai (`ap-south-1a/b` Multi-AZ) | AES-256-GCM Column Encryption |
| **Encrypted Media Vault** | Private S3 Bucket | India | Mumbai (`ap-south-1`) | Object Lock, KMS Customer Managed Keys |
| **Voice Streaming & Inference**| Regional Edge Gateway | India | Domestic Edge Nodes | Ephemeral RAM streaming; zero disk caching |

---

## 2. Contact List Protection & Cryptographic Isolation

Contact directories uploaded via CSV or CRM sync are treated as **Sensitive Personal Data (SPD)**.

### A. Envelope Encryption Pipeline
1. **At Rest**:
   - Phone numbers and recipient full names are encrypted before persistence using **AES-256-GCM** with unique initialization vectors (IVs).
   - Cryptographic keys are rotated via Hardware Security Module (HSM) / AWS Key Management Service (KMS).
   - In database queries and analytical dashboards, phone numbers are masked using irreversible salted SHA-256 hashes (`+91 98••• ••210`) with an obfuscated terminal display.
2. **In Transit**:
   - All REST APIs, WebSockets, and database ingress require **TLS 1.3** with forward secrecy (`ECDHE-RSA-AES256-GCM-SHA384`).
   - Telephony webhooks from Exotel validate cryptographic HMAC-SHA1 signatures and source IP whitelisting.

---

## 3. Audio Recording Security & Media Lifecycle

Telephony recordings present significant data aggregation risks if left on public carrier infrastructure.

```
       [Call Concluded on Exotel]
                   │
                   ▼ (StatusCallback with short 15-min presigned URL)
       [Platform Ingestion Worker]
                   │
                   ├─► 1. Stream encrypted audio directly to private S3 vault (AES-256-GCM)
                   │
                   ├─► 2. Issue immediate HTTP DELETE request to Exotel carrier storage
                   │      (Purges audio from telecom servers within < 60 seconds)
                   │
                   ├─► 3. Execute streaming PII/PHI Named Entity Recognition (NER)
                   │      (Redacts credit card numbers, OTPs, medical specialties from transcript & audio)
                   │
                   └─► 4. Apply retention policy: Auto-purge after 30 days unless legal hold active
```

---

## 4. Answering Machine Detection (AMD) & HIPAA/DPDPA Voicemail Rules

Under the HIPAA Privacy Rule (45 CFR § 164.502) and DPDPA, voicemails recorded on answering machines can be overheard by household members or third parties.

| Call State | Permissible Voice Content | Prohibited Voice Content |
| :--- | :--- | :--- |
| **Live Human Respondent** | Patient/Recipient full name, appointment date/time, doctor name, clinic address, interactive rescheduling options. | Unrelated medical history, sensitive diagnosis disclosure. |
| **Answering Machine / Voicemail** | Recipient first name, organization name, callback telephone number, generic confirmation request. | **Medical specialties** (e.g. "Oncology Department", "Psychiatric Clinic"), diagnosis, test results, prescription names. |

### Compliant Voicemail Template:
> *"Hello, this is an automated notification for John from City Health Center. You have an appointment scheduled for Tuesday, October 13th at 10:00 AM. Please call 080-4567-8900 to confirm or reschedule. Thank you."*

---

## 5. DPDPA Consent & Automated Right-to-Erasure Pipeline

1. **Mandatory Acoustic Notice**:
   Every outbound call begins with a clear notification:
   > *"This automated call is processed by AI for event registration and may be recorded. To opt out, press 9 or disconnect."*
2. **Consent Ledger**:
   Recipient actions are committed to an immutable append-only ledger (`consent_audit_log`):
   - `recipient_token`, `timestamp_utc`, `notice_version`, `status` (`ACCEPTED`, `OPT_OUT_DTMF_9`, `OPT_OUT_VERBAL`).
3. **Automated Right-to-Erasure Execution**:
   When a recipient presses `9` or speaks *"Opt out" / "Stop calling"*:
   - Phone number is immediately moved to a global **Permanent Suppression List**.
   - Contact records, interaction history, and audio recordings for that identifier are cryptographically purged across all active tables.
   - An immutable cryptographic receipt (SHA-256 hash of the deletion event) is generated for compliance verification.
