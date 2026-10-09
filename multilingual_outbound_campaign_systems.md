# Architectural Blueprint and Engineering Specification for Multilingual Outbound Campaign Systems

## Deliverables Specification and Functional Requirements Analysis

The development mandate defined in specification PR 002 requires an automated communications platform capable of translating campaign templates and recipient registries into scalable, multilingual outbound calling campaigns. The platform must execute these operations with minimal administrative overhead while supporting high-stakes operational environments, including academic seminars, clinical appointment notifications, educational institutional broadcasts, and debt recovery workflows.

The core technical deliverables comprise six interconnected subsystems. The campaign orchestration engine serves as the administrative entry point, ingesting audience parameters, localized scripts, and demographic variables to generate structured outreach schedules. The telephony abstraction layer provides direct integration with Exotel infrastructure, executing automated batch calling, line allocation, and call lifecycle event monitoring. The intent detection engine processes recipient feedback across both dual-tone multi-frequency (DTMF) keypad signals and continuous acoustic speech streams. The voicemail and answering machine classification system isolates automated inboxes from live respondents to apply compliant message routing. The operational analytics dashboard delivers real-time visibility into campaign throughput across linguistic and demographic cohorts, incorporating automated retry mechanisms. Finally, the data protection layer enforces cryptographic isolation, transient media scrubbing, and regulatory compliance under both the Digital Personal Data Protection Act (DPDPA) and the Health Insurance Portability and Accountability Act (HIPAA).

| Functional Subsystem | Required Technical Deliverable | Operational Artifact Produced | Telephony and Infrastructure Dependency |
| --- | --- | --- | --- |
| **Campaign Management** | Dynamic template ingestion API, variable substitution mapper, and audience segment parser. | Normalized outreach campaign payloads and scheduled execution queues. | Campaign relational store, Redis task queue. |
| **Telephony Dispatcher** | Outbound calling client consuming Exotel Campaigns API (`v2`) and Voice API (`v1`/`v3`). | Live outbound sessions, Call Detail Records (CDRs), and event streams. | Exotel REST API endpoints (`@api.in.exotel.com`). |
| **Intent Processing** | Dual-modality ingestion handling DTMF via Passthru applets and speech via WebSocket streaming. | Standardized intent classification tokens (`CONFIRM`, `RESCHEDULE`, `DECLINE`). | Exotel App Bazaar (`Passthru`, `Voicebot` applets). |
| **Voicemail Engine** | Signal classifier consuming carrier AMD parameters and acoustic energy patterns. | Disposition markers distinguishing live humans from automated inboxes. | Exotel StatusCallback AMD metadata. |
| **Analytics Dashboard** | Analytical interface visualizing connect rates, language breakdowns, and retry controls. | Aggregate campaign reports and automated retry candidate manifests. | High-throughput time-series store, React frontend. |
| **Data Governance** | Cryptographic envelope pipeline, PII/PHI redaction worker, and audit logging engine. | Encrypted media stores, sanitized transcripts, and verifiable deletion proofs. | Key Management Service (KMS), S3-compatible private object vault. |

## Interaction Modality Architecture: Pre-Recorded Prompts, Dynamic IVR, and Conversational Voice Agents

Determining the acoustic interaction modality requires evaluating the trade-offs among engineering complexity, operational expenses, latency budgets, and linguistic versatility across regional dialects. Specification PR 002 permits static pre-recorded prompts, dynamic text-to-speech (TTS) interactive voice responses (IVR), full conversational voice agents, or hybrid implementations.

| Architecture Option | Latency Budget (Turn-Taking) | Multilingual Flexibility | Variable Insertion Capability | Concurrency and Compute Cost Profile | User Friction and Completion Rate |
| --- | --- | --- | --- | --- | --- |
| **Static Pre-recorded Audio** | Zero compute latency (<50 ms carrier transit). | Minimal; requires manual studio recording for every regional language. | Rigid; cannot concatenate arbitrary dates, names, or balances dynamically. | Minimal compute overhead; bounded strictly by base carrier calling rates. | High drop-off; rigid menu navigation is frequently perceived as spam. |
| **Dynamic TTS-Driven IVR** | Low (<200 ms for synthetic streaming). | High; programmatic neural voice generation across regional dialects. | Complete; variables are interpolated directly into synthesized text strings. | Predictable and cost-effective; negligible CPU load for audio playback. | Moderate friction; keypad reliance limits nuanced conversational inputs. |
| **Conversational Voice AI Agent** | Variable (600 ms – 1400 ms roundtrip). | Exceptional; dynamic multi-turn code-switching and dialect comprehension. | Native; large language models dynamically contextualize arbitrary variables. | High compute cost; requires dedicated streaming server infrastructure. | Minimal friction; achieves superior completion for unstructured responses. |
| **Deterministic-First Hybrid Model** | Near-zero initial prompt latency; 500 ms conversational fallback. | High; standardized neural TTS core paired with conversational fallback. | High; dynamic synthesis of structural variables with deterministic slots. | Balanced; reserves resource-intensive inference for ambiguous speech. | Optimal; combines deterministic compliance with conversational forgiveness. |

Deploying an autonomous, end-to-end conversational voice agent across thousands of outbound calls introduces significant operational vulnerabilities. Real-time speech pipelines running across public carrier networks remain vulnerable to latency jitter, acoustic packet loss, regional accent misinterpretations, and non-deterministic model hallucinations. In regulated environments, such as medical notifications or payment reminders, an unconstrained language model can introduce serious compliance liabilities. Conversely, traditional static IVR systems exhibit severe user drop-off in multilingual markets, where users routinely ignore structured keypad menus and respond with natural spoken phrases.

The recommended architecture is a deterministic-first hybrid state machine. Under this operational pattern, the outbound call initiates with a high-fidelity synthetic TTS audio prompt that articulates the core transactional purpose of the call. The recipient is presented with concurrent input pathways, allowing them to confirm via keypad entry or spoken confirmation. If a DTMF digit is detected, the system executes an immediate state transition with zero machine-learning latency. If acoustic energy is detected instead, an ephemeral speech recognition worker captures the utterance, maps the phrase against a constrained semantic intent classifier, and executes the appropriate state transition. The system escalates to an interactive, multi-turn conversational agent over WebSockets only when the user's response falls outside predefined semantic boundaries or requests additional context.

## Computational Feasibility of Local and CPU-Only Artificial Intelligence

Running real-time voice AI pipelines entirely on local CPU hardware presents severe computational challenges that directly degrade conversational naturalness. Evaluating this approach requires analyzing the acoustic roundtrip latency against the human perceptual threshold for interactive telephone conversations.

### Latency Budget and Pipeline Bottlenecks

Maintaining a natural conversational rhythm over telephony channels requires an end-to-end turn-taking latency below 700 milliseconds, with 1000 milliseconds representing the absolute functional limit. The total system latency is determined by the cumulative duration of several distinct pipeline operations:

$$
\text{Latency}_{\text{Total}} = \text{Network}_{\text{Ingress}} + \text{VAD} + \text{ASR} + \text{LLM}_{\text{TTFT}} + \text{TTS}_{\text{FirstChunk}} + \text{Network}_{\text{Egress}}
$$

Voice Activity Detection (VAD) requires an acoustic silence window of 150 to 200 milliseconds to confirm that the speaker has concluded an utterance. Telephony network transport, jitter buffering, and WebSocket frame serialization contribute another 50 to 100 milliseconds. This leaves a strict processing budget of approximately 400 to 500 milliseconds across the remaining inference stages:

Automatic speech recognition using `faster-whisper` with 8-bit quantization on server-grade x86 CPUs achieves a Real-Time Factor (RTF) between 0.20 and 0.35. Transcribing a two-second voice sample requires approximately 400 to 700 milliseconds of raw CPU compute time. Quantized 8-billion parameter language models executed via `llama.cpp` using AVX-512 vector instructions achieve a Time-to-First-Token (TTFT) between 300 and 550 milliseconds under unloaded conditions. Highly optimized local speech synthesis engines, such as Piper TTS, operate with an RTF below 0.08, requiring 80 to 120 milliseconds to generate the first audio buffer.

Cumulatively, an optimized local CPU-only pipeline incurs an end-to-end response delay between 1,080 and 1,670 milliseconds. This latency profile consistently causes speech collisions over standard telephone lines, as callers assume the line has disconnected and resume speaking just as synthetic audio playback begins.

| Hardware and Orchestration Strategy | ASR Latency (2s audio) | LLM TTFT | TTS First Byte | Roundtrip Latency (Total) | Maximum Concurrent Streams per Node | Production Feasibility |
| --- | --- | --- | --- | --- | --- | --- |
| **Local CPU-Only** (AVX-512, INT8, EPYC 32-core) | 450 – 700 ms | 350 – 550 ms | 80 – 120 ms | **1,080 – 1,670 ms** | 2 – 4 calls per host (saturates AVX pipelines) | Unfeasible for natural voice; viable only for sequential turn-taking. |
| **Local CPU (Constrained SLM)** (Whisper-Tiny + 1B SLM + Piper) | 200 – 300 ms | 120 – 180 ms | 60 – 90 ms | **580 – 870 ms** | 6 – 10 calls per host | Marginally viable; poor multilingual comprehension in Indian languages. |
| **Local Accelerated** (Single NVIDIA L4 / TensorRT-LLM) | 80 – 140 ms | 40 – 70 ms | 40 – 60 ms | **360 – 520 ms** | 40 – 60 calls per host | Production-grade; maintains total on-premise data isolation. |
| **Specialized Cloud Voice APIs** (Deepgram/Sarvam + Hosted LLM + Cartesia) | 100 – 180 ms | 60 – 100 ms | 50 – 90 ms | **410 – 620 ms** | Elastic scaling (bounded by account API rate limits) | Production-grade; minimal infrastructure maintenance overhead. |

### Concurrency Contention and Enterprise Deployment Realities

Beyond aggregate turn-around latency, local CPU execution encounters severe performance degradation when processing concurrent telephone channels. ASR and LLM matrix calculations fully saturate available CPU cores via vectorized execution units. When multiple calls arrive simultaneously, thread contention spikes response latency from 1.2 seconds to over 4 seconds, causing real-time WebSocket buffers to underflow and drop carrier connections.

Production deployments address this constraint by decoupling control logic from real-time inference:

When regulatory compliance requires strict on-premise execution, organizations deploy edge servers equipped with enterprise GPU accelerators (such as NVIDIA L4 hardware). These systems run accelerated inference engines like TensorRT-LLM alongside optimized speech models, maintaining sub-500 millisecond response budgets while keeping audio within local server boundaries.

For standard production platforms where cloud processing is permitted, engineering teams implement hybrid cloud topologies. Campaign metadata, database records, and call flow routing remain on private infrastructure, while media streams route through low-latency regional APIs (such as Sarvam AI or Deepgram for multilingual Indian phoneme tracking) to satisfy conversational latency constraints.

## Telephony Orchestration and Exotel Integration Mechanics

Integrating with Exotel infrastructure requires coordinating asynchronous REST campaign triggers, synchronous call injection endpoints, App Bazaar call flows, and real-time media streaming interfaces.

### Outbound Call Initialization Paths

The platform implements two calling mechanisms based on campaign volume and operational requirements:

High-volume event reminders and educational broadcasts utilize Exotel's Campaigns API (`v2`), targeting regional endpoints such as `https://@api.in.exotel.com/v2/accounts/{AccountSid}/campaigns`. The platform constructs an administrative JSON payload containing the sender identity, recipient arrays, retry policies, and the target App Bazaar call flow URL:

```json
{
  "name": "Seminar_Invitation_Cohort_A",
  "caller_id": "080XXXXXXXX",
  "url": "http://my.exotel.com/{AccountSid}/exoml/start_voice/{AppId}",
  "type": "trans",
  "from": ["+9198XXXXXXXX", "+9197XXXXXXXX"],
  "retries": {
    "number_of_retries": 2,
    "interval_mins": 30
  }
}
```

Exotel orchestrates outbound pacing, telecom line allocation, and automated redialing for busy or unreachable numbers.

For time-sensitive transactional events—such as urgent clinical appointment notifications or password verification alerts—the system bypasses batch queues and invokes Exotel's Voice API directly via `POST https://api.in.exotel.com/v1/Accounts/{AccountSid}/Calls/connect.json`. This request passes `From`, `CallerId`, `Url`, and an asynchronous `StatusCallback` webhook URL, establishing immediate, single-call sessions.

### Dynamic Call Flow Orchestration via App Bazaar

To support dual-modality interaction, call flows configured within Exotel's App Bazaar link several core functional applets:

The call opens with a Passthru applet that issues a synchronous HTTP GET or POST request to the campaign backend, transmitting session metadata including `CallSid`, `CallFrom`, `CallTo`, and custom tracking identifiers. The backend queries recipient records to retrieve language preferences and context-specific variables, returning routing decisions that dynamically branch downstream execution.

Calls route to a Gather applet to deliver localized synthetic prompts and capture DTMF keypad entries, using configurable timeout windows and digit length constraints. If the campaign requires real-time conversational voice processing, the flow directs media to a Voicebot applet, which establishes a bidirectional WebSocket connection to the streaming backend.

### Real-Time WebSocket Streaming Specifications

When engaging the Voicebot applet, Exotel establishes an upstream WebSocket connection (`wss://`) to the platform's media handling server. The stream adheres to standardized carrier audio specifications:

Audio data flows as 16-bit linear PCM encoded at an 8,000 Hz (8 kHz) sampling rate across a single mono channel. Audio frames arrive in packetized chunks—typically 20-millisecond or 60-millisecond intervals—transmitted as binary frames or serialized within JSON envelopes containing stream metadata.

During the initial connection handshake, the server extracts session parameters, including `stream_id`, `call_id` (matching Exotel’s `CallSid`), and terminal telephone numbers. The ingestion pipeline upsamples incoming 8 kHz audio to 16 kHz for ASR model consumption, while synthetic TTS audio is downsampled back to 8 kHz mono before streaming outbound chunks over the WebSocket back to Exotel.

### Answering Machine Detection and Webhook Handling

To prevent automated systems from consuming carrier minutes and human resources, the platform uses Exotel's Answering Machine Detection (AMD) engine. AMD analyzes the initial two to three seconds of acoustic energy following connection, evaluating silence duration, greeting length, and frequency characteristics to differentiate human voices from automated recordings.

When a call concludes, Exotel dispatches an HTTP POST payload to the platform's `StatusCallback` URL, reporting call duration, recording references, and AMD classification metrics:

```json
{
  "CallSid": "80bfbec2d78bbbf10fb851f4fa165211",
  "Status": "completed",
  "EventType": "terminal",
  "RecordingUrl": "https://s3-ap-southeast-1.amazonaws.com/exotel-recordings/...",
  "Legs": [
    {
      "OnCallDuration": 32,
      "Status": "completed",
      "AnsweredBy": "Human"
    }
  ],
  "CustomField": "camp_942_user_8810"
}
```

If `AnsweredBy` returns `Machine`, the campaign engine flags the interaction as an automated inbox. Depending on campaign rules, the system either terminates the session immediately (standard practice for debt recovery and event RSVP calls) or leaves an abbreviated, compliant notification (standard practice for clinical reminders).

## Data Privacy, Cryptographic Isolation, and PHI/PII Governance

Deploying automated calling systems across clinical, educational, and financial environments requires comprehensive data governance. Contact registries, audio recordings, and interaction transcripts constitute protected personal data under India’s Digital Personal Data Protection Act (DPDPA 2023) and Protected Health Information (PHI) under HIPAA.

### Healthcare Compliance and Voicemail Scripts

Under the HIPAA Privacy Rule, routine appointment reminders fall under treatment communications, exempting them from general marketing consent requirements. However, these communications remain bound by the *Minimum Necessary Standard*.

Depositing automated voicemails presents compliance challenges because recorded messages can be accessed by unintended third parties. The system must alter its messaging based on whether the recipient is verified as a live patient or identified as an automated recording:

| Recipient State | Permissible Content (HIPAA & DPDPA Boundaries) | Strictly Prohibited Content |
| --- | --- | --- |
| **Live Verified Patient** (Identity confirmed via secondary challenge, e.g., birth year or DTMF verification). | Patient name, provider name, clinic facility, confirmed appointment date, check-in instructions, and dynamic rescheduling options. | Disclosures of unrelated medical conditions, sensitive diagnostic details, or historical clinical findings. |
| **Answering Machine / Voicemail Drop** (Unverified inbox access). | Patient first name, healthcare practice name, callback phone number, and a generic confirmation request. | **Medical specialties** (e.g., "Oncology Clinic"), specific procedures, diagnoses, test results, or physician specialty designations. |

Compliant automated voicemail scripts exclude all clinical context, delivering only basic operational instructions:

> "This is an automated reminder for John from City Health Center. You have an appointment scheduled for Tuesday, October 13th at 10:00 AM. Please call 555-0199 to confirm or reschedule."

### Cryptographic Pipelines and Data Storage Lifecycles

Protecting contact directories and acoustic recordings requires complete data isolation across their lifecycle:

All administrative API interactions, webhook callbacks, and WebSocket media sessions must use TLS 1.3 with strict cipher suites. Ingress endpoints validate requests using mutually authenticated TLS (mTLS) or Basic Authentication reinforced by IP-address whitelisting.

Because audio files stored on carrier infrastructure present data aggregation risks, the platform configures Exotel recording URLs with short Time-To-Live (TTL) presigned access windows, restricted to between 5 and 60 minutes. A background worker downloads newly generated recordings immediately upon webhook arrival, confirms transfer, and purges the file from carrier storage.

Downloaded media and generated transcripts are transferred to dedicated object stores using AES-256-GCM encryption, managed by hardware security modules (HSM) or Key Management Services (KMS). Relational database stores enforce column-level encryption for all recipient phone numbers, national identification markers, and patient names. Audio files pass through a streaming Named Entity Recognition (NER) pipeline that transcribes text, identifies sensitive entities (such as names, dates, phone numbers, and payment details), and redacts both the text transcripts and the corresponding audio frequencies before analytical indexing.

### DPDPA Mandates and Regulatory Data Localization

Under India's DPDPA (and the DPDP Rules), the campaign platform functions as a Data Processor on behalf of the deploying organization (the Data Fiduciary). Compliance requires strict operational safeguards:

All voice streaming, speech recognition, language model inference, and relational databases must reside within domestic borders. Telephony requests route through Exotel’s domestic Mumbai cluster (`@api.in.exotel.com`), while backend servers operate in local data regions (such as AWS `ap-south-1`).

Prior to processing conversational turns, outbound calls deliver a clear, concise notice: *"This automated call is processed by AI for event registration and may be recorded. To opt out, press 9 or disconnect"*. The recipient's response is committed to an append-only audit table logging the timestamp, notice version, and consent status.

When a recipient requests data deletion—either via DTMF opt-out, conversational request, or formal erasure request—an automated pipeline purges the user's phone records, call logs, recording files, and semantic indexes, producing a verifiable audit proof of deletion.

## Analytics Dashboard Architecture and Algorithmic Recovery Workflows

The campaign dashboard tracks operational throughput, linguistic performance, and audience sentiment, providing administrators with real-time controls to manage outbound campaigns.

### Performance Metrics Hierarchy and Disposition Taxonomy

Call Detail Records are normalized into standardized disposition states to support detailed cohort analysis:

| Primary Dimension | Sub-Segment | Granular Disposition Code | Downstream System Action |
| --- | --- | --- | --- |
| **Call Delivery Status** | Carrier Ingress | `COMPLETED_LIVE_HUMAN` | Route session to the Intent Processing Pipeline. |
|  | Carrier Ingress | `ANSWERED_MACHINE` | Leave voicemail drop or terminate; queue for optional SMS follow-up. |
|  | Network Exception | `NETWORK_BUSY` | Route record into Exponential Backoff Retry Queue. |
|  | Network Exception | `NO_ANSWER_TIMEOUT` | Increment attempt counter; reschedule for secondary calling window. |
|  | Terminal Failure | `INVALID_NUMBER` | Flag record as dead; permanently suppress from future campaigns. |
| **Recipient Intent** | Semantic Outcome | `INTENT_CONFIRMED` | Commit positive confirmation; trigger calendar invite and confirmation SMS. |
|  | Semantic Outcome | `INTENT_DECLINED` | Update CRM registry; remove from subsequent outreach cycles. |
|  | Semantic Outcome | `INTENT_RESCHEDULE` | Escalate to human support desk or dispatch dynamic scheduling link. |
|  | Semantic Outcome | `INTENT_AMBIGUOUS` | Flag for review or assign to manual agent follow-up queue. |
| **Demographic Tier** | Localization | `LANG_REGIONAL_HINDI` | Measure model comprehension against conversion rates across dialects. |
|  | Segmentation | `TIER_1_PRIORITY` | Route directly to dedicated senior agents upon intent failure. |

### Algorithmic Retry Policies for Non-Responders

Achieving high contact rates requires structured retry policies that optimize reach while preventing carrier spam labeling and compliance violations. The dashboard retry engine operates under deterministic scheduling parameters:

Outbound calls are restricted to approved daytime windows (typically 9:00 AM to 8:00 PM local time), automatically suspending retries until the next approved period. The retry interval $\Delta t_{\text{retry}}$ dynamically scales based on the terminal failure code:

$$
\Delta t_{\text{retry}} = \begin{cases} 20 \text{ minutes} & \text{if Disposition} = \text{NETWORK\_BUSY} \\ 120 \text{ minutes} & \text{if Disposition} = \text{NO\_ANSWER\_TIMEOUT} \\ \infty \text{ (Suppress)} & \text{if Disposition} \in \{\text{INVALID\_NUMBER}, \text{OPT\_OUT}\} \end{cases}
$$

If an outreach attempt fails after two consecutive voice attempts, the system pauses voice dialing and triggers an automated omnichannel fallback via SMS or WhatsApp containing an interactive self-service link.

## Enterprise Implementation Strategy

Building an enterprise-ready outbound campaign platform requires establishing stable telephony primitives before introducing complex real-time AI capabilities. Development should follow a structured three-phase roadmap:

The initial implementation focuses on establishing core telephony workflows using Exotel's Campaigns API (`v2`), integrating the Gather and Passthru applets to handle structured DTMF user input. This baseline validates number provisioning, AMD accuracy, carrier retries, and storage encryption before introducing real-time audio streaming.

The second phase integrates real-time bidirectional media streaming via Exotel's Voicebot applet. Deploying a hybrid architecture backed by accelerated cloud services or dedicated on-premise GPU inference instances introduces natural speech parsing and dynamic language switching for incoming user responses.

The final phase introduces the operational analytics interface, connecting call disposition metrics to automated retry workflows and multi-channel failover paths. This phase concludes by activating automated DPDPA compliance routines, verifying that recipient contact records, call recordings, and analytical metadata can be audited, protected, and deleted in full accordance with regulatory standards.
