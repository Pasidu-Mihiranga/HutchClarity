# Hutch Clarity - Architecture Diagrams

[← 04-enterprise-architecture.md](04-enterprise-architecture.md) · [← Plan index](README.md) · [06-integration-tmf.md →](06-integration-tmf.md)

> Part of the **Hutch Clarity Enterprise Project Plan**. Labels: `[DECK Sx]` = stated in deck slide x · `[PROPOSED]` = expanded by this plan · **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION** / **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**. See the [index](README.md) for the full legend.

> **Plan v1.1 (2026-10-01).** Updated to match [17](17-build-blueprint.md), [18](18-tech-stack-and-ai.md) and [19](19-policy-change-management.md). Change record: [CHANGES.md](CHANGES.md).

## 8. Architecture Diagrams

All diagrams are created for this plan (`[PROPOSED]`), based on deck slides 4, 7, 8, 11, 12 and 14.

### Diagram 1 - High-Level Solution Architecture

```mermaid
flowchart TB
    subgraph CH["Channels"]
        WEB["Website hutch.lk"]
        APP["Hutch app WebView"]
        WA["WhatsApp text + voice"]
        SMS["SMS / USSD"]
        DESK["Clarity Desk"]
        OPS["Ops console"]
    end
    ORCH["Orchestration<br/>identity · language · batching · handoff · router"]
    subgraph CORE["Clarity Core - deterministic, versioned, audited"]
        TL["Timeline Builder<br/>8 sources"]
        CD["Cause Detectors<br/>versioned rules"]
        DP["Decision Policy<br/>confidence · caps"]
        TOOL["Tool Layer<br/>idempotent actions"]
        TR["Trust Receipts<br/>signed · QR · replay"]
    end
    subgraph AI["AI Services - language and patterns only"]
        LLM["Language LLMs<br/>extract · explain"]
        MCP["Clarity MCP Server"]
        AUT["Complaint Autopsy"]
        FOR["Foresight"]
    end
    ADP["Integration Adapters<br/>TM Forum-shaped · read-first"]
    HS["HUTCH Systems<br/>Payments · Charging · Catalogue · VAS · Usage · CRM"]
    DATA["Data Platform<br/>PostgreSQL+pgvector · Valkey · Kafka · Warehouse"]

    CH --> ORCH --> TL --> CD --> DP --> TOOL --> TR
    ORCH <--> LLM
    LLM <--> MCP
    MCP -->|"read tools / propose only"| CORE
    AUT --> CD
    FOR <--> AUT
    TL --> ADP
    TOOL -->|"writes only here"| ADP
    ADP --> HS
    CORE --- DATA
    AI --- DATA

    classDef det fill:#F7931E,stroke:#B85C00,color:#000
    classDef ai fill:#D9D9D9,stroke:#777,color:#000
    classDef proof fill:#C2410C,stroke:#7C2D12,color:#fff
    class TL,CD,DP,TOOL det
    class LLM,MCP,AUT,FOR ai
    class TR proof
```

### Diagram 2 - Detailed Enterprise Architecture

```mermaid
flowchart LR
    subgraph INTERNET["Internet"]
        C1["Customer web/app"]
        C2["WhatsApp Cloud API"]
        C3["SMS/USSD via HUTCH SMSC/USSD GW"]
        S1["Staff browser / mobile"]
    end
    subgraph EDGE["Edge zone"]
        WAF["CDN + WAF + bot mgmt"]
        GW["API Gateway<br/>rate limits · JWT validation"]
        WH["Webhook receiver<br/>signature check"]
    end
    subgraph APPZ["Application zone - Kubernetes"]
        FE["Next.js PWA<br/>web · app module · Desk · Ops"]
        IDB["Identity broker<br/>OTP · SSO/OIDC"]
        ORC["Conversation orchestrator<br/>session · language · router · handoff"]
        CASE["Case service"]
        TLB["Timeline builder"]
        RULE["Rule engine"]
        OPA["OPA decision + authz"]
        TOOLS["Tool layer + outbox"]
        RCPT["Receipt service"]
        SIGN["Signing service"]
        REC["Reconciliation job"]
        DESKAPI["Desk API<br/>approvals · bulk · what-if"]
        MCPS["MCP server"]
    end
    subgraph AIZ["AI zone"]
        AIGW["AI gateway<br/>router · quota · masking check"]
        PII["PII masking + token vault"]
        VER["Output verifier"]
        SLM["LLM providers by role<br/>Gemini · Groq · HUTCH models"]
        RAG["RAG retriever"]
        STT["STT / TTS"]
        AUT["Autopsy workers"]
        FOR["Foresight sandbox"]
    end
    subgraph DATAZ["Data zone"]
        PG[("PostgreSQL 18<br/>schema per module · ledger · pgvector")]
        RD[("Valkey<br/>sessions · cache · idempotency")]
        KF[("Kafka + Apicurio registry")]
        OBJ[("Object storage WORM")]
        WH2[("Analytics warehouse")]
    end
    subgraph INTZ["Integration zone"]
        ADP["Adapters - mTLS<br/>payments · charging · catalogue · vas · usage · crm · notify"]
    end
    subgraph HUTCH["HUTCH systems - REQUIRES CONFIRMATION"]
        HSYS["OCS · Payment GW · Catalogue · DCB/VAS · CDR/PCRF · CRM · IAM"]
    end
    EXT["Hosted LLM tier<br/>masked text only"]

    C1 --> WAF --> GW --> FE
    S1 --> WAF
    C2 --> WH
    C3 --> WH
    GW --> IDB
    GW --> ORC
    WH --> ORC
    FE --> GW
    ORC --> CASE --> TLB --> ADP
    TLB --> RULE --> OPA --> TOOLS --> ADP
    TOOLS --> RCPT --> SIGN
    ORC --> AIGW
    AIGW --> PII
    AIGW --> SLM
    AIGW --> EXT
    AIGW --> VER
    AIGW --> RAG
    ORC --> STT
    AIGW <--> MCPS
    MCPS --> OPA
    MCPS --> CASE
    DESKAPI --> OPA
    DESKAPI --> TOOLS
    ADP --> HSYS
    CASE --- PG
    TOOLS --- KF
    ORC --- RD
    RCPT --- OBJ
    KF --> AUT
    KF --> WH2
    WH2 --> FOR
    REC --> ADP
```

### Diagram 3 - Customer Dispute Request Flow

```mermaid
sequenceDiagram
    autonumber
    actor Cu as Customer
    participant Ch as Channel (app/WhatsApp)
    participant Or as Orchestrator
    participant Ca as Case Service
    participant Tl as Timeline Builder
    participant Ad as Adapters
    participant Ru as Rule Engine
    participant Po as Decision Policy (OPA)
    participant Ai as AI Gateway + Verifier
    participant To as Tool Layer
    participant Rc as Receipt Service

    Cu->>Ch: Tap Why? on -LKR 49 (or voice/text)
    Ch->>Or: request + session token
    Or->>Or: identity check, language detect, handoff check
    Or->>Ca: create/attach case (charge_ref)
    Ca->>Tl: build timeline(window)
    par parallel reads
        Tl->>Ad: payments / charging / vas consent / usage / catalogue
    end
    Ad-->>Tl: normalized events + completeness flags
    Tl-->>Ca: timeline snapshot (hash)
    Ca->>Ru: evaluate active rule bundle
    Ru-->>Ca: ranked causes + ruled-out + evidence refs
    Ca->>Po: decide(causes, amount, risk, completeness)
    Po-->>Ca: ONE_TAP_FIX, allowed actions
    Ca->>Ai: explain(facts JSON, language=si)
    Ai-->>Ca: masked draft -> verifier OK (else template)
    Ca-->>Ch: reason + evidence + proposed fix
    Cu->>Ch: Confirm
    Ch->>Or: confirmation (UI-minted token)
    Or->>To: execute(action, idempotency_key, confirmation)
    To->>Ad: refund / deactivate / block
    Ad-->>To: success refs
    To->>Rc: action.completed
    Rc-->>Ch: Trust Receipt (signed, QR)
```

### Diagram 4 - Decision Engine Flow

```mermaid
flowchart TD
    A["Ranked causes + evidence"] --> B{"Evidence complete<br/>for top cause?"}
    B -- No --> H1["HAND-OFF / HOLD<br/>missing log -> human"]
    B -- Yes --> C{"Fraud flag or<br/>recent SIM swap?"}
    C -- Yes --> S["STAFF APPROVAL"]
    C -- No --> D{"Top two causes<br/>within margin?"}
    D -- Yes --> S
    D -- No --> E{"Customer-visible rule<br/>disclosed at purchase?"}
    E -- Yes --> X["EXPLAIN ONLY"]
    E -- No --> F{"Confidence >= threshold?"}
    F -- No --> S
    F -- Yes --> G{"Amount <= auto cap<br/>and budget available?"}
    G -- No --> S
    G -- Yes --> I{"Money back only<br/>no service change?"}
    I -- Yes --> AF["AUTO-FIX"]
    I -- No --> OT["FIX WITH ONE TAP<br/>customer confirms"]
    S --> J{"Amount > finance threshold?"}
    J -- Yes --> K["Four-eyes: supervisor + finance"]
    J -- No --> L["Supervisor approval"]
    Q["Customer asks for a person"] --> H2["HAND-OFF"]
```

### Diagram 5 - AI + Deterministic Rule Boundary

```mermaid
flowchart LR
    subgraph LLMZONE["AI zone - may read masked data, may NOT decide or move money"]
        X1["Intake extraction<br/>hints only"]
        X2["Explanation drafting"]
        X3["Summaries, replies"]
        X4["RAG answers with citations"]
        X5["Autopsy summaries, cluster labels"]
        X6["Foresight personas"]
    end
    subgraph DETZONE["Deterministic zone - decides and moves money"]
        D1["Timeline from system records"]
        D2["Cause rules"]
        D3["Decision policy + caps + budgets"]
        D4["Tool layer"]
        D5["Numeric verifier"]
        D6["Receipt signing"]
    end
    X1 -- "candidate filters only" --> D1
    D1 --> D2 --> D3 --> D4 --> D6
    D3 -- "facts JSON" --> X2
    X2 -- "draft text" --> D5
    D5 -- "pass" --> OUT["Customer reply"]
    D5 -- "fail" --> TPL["Approved template"] --> OUT
    X3 -.->|"propose_action only"| D3
    BAN["Text is a hint, never evidence"]:::note
    classDef note fill:#fff,stroke:#C2410C,stroke-dasharray: 4 4
```

### Diagram 6 - MCP Architecture

```mermaid
flowchart TB
    LLM["LLM / AI agent<br/>self-hosted or hosted tier"] --> ORC["AI Orchestrator<br/>prompt assembly · tool loop"]
    ORC --> CLI["MCP client<br/>bound to session principal"]
    subgraph SRV["Hutch Clarity MCP Server"]
        AUTH["AuthN: token -> principal + profile"]
        ALLOW["Tool allowlist per profile<br/>customer-assist · staff-assist · analytics"]
        SCH["Pydantic schema validation"]
        POL["OPA policy: authz · scope · rate · safety level"]
        IDEM["Idempotency + correlation IDs"]
        AUD["MCPInvocation audit"]
        T1["L1 read tools"]
        T2["L2 low-risk tools"]
        T3["propose_action - creates pending proposal"]
    end
    CLI -->|"Streamable HTTP + mTLS + OAuth token"| AUTH
    AUTH --> ALLOW --> SCH --> POL --> IDEM
    IDEM --> T1
    IDEM --> T2
    IDEM --> T3
    T1 --> CORE["Clarity Core APIs<br/>case · timeline · rules · receipts · RAG"]
    T2 --> CORE
    T3 --> PEND["Pending action store"]
    PEND --> CONF["Confirmation outside LLM<br/>customer tap or Desk approval + MFA"]
    CONF --> TOOLS["Tool layer"]
    TOOLS --> ADP["Adapters -> mock or HUTCH systems"]
    CORE --> ADP
    POL -.-> AUD
    T1 -.-> AUD
    T2 -.-> AUD
    T3 -.-> AUD
```

### Diagram 7 - HUTCH Integration Architecture

```mermaid
flowchart LR
    subgraph CL["Hutch Clarity"]
        TLB["Timeline builder"]
        TOOLS["Tool layer"]
        NOTI["Notification service"]
        IDB["Identity broker"]
    end
    subgraph AL["Integration adapter layer - canonical TMF-shaped contracts"]
        PAY["Payment adapter<br/>TMF676-shaped"]
        CHG["Charging adapter<br/>TMF635-shaped usage/charges"]
        CAT["Catalogue adapter<br/>TMF620 / TMF637"]
        VAS["VAS consent adapter<br/>DCB · OTP evidence"]
        USE["Usage/FUP adapter<br/>CDR · PCRF state"]
        CRM["CRM/Ticket adapter<br/>TMF621 / TMF629"]
        NOT["Notification adapter<br/>TMF681 · SMSC · USSD"]
        IDA["Identity / risk adapter<br/>OTP · SIM-swap"]
    end
    subgraph IF["Approved enterprise interfaces - REQUIRES HUTCH CONFIRMATION"]
        ESB["HUTCH API gateway / ESB / DB views / event streams"]
    end
    subgraph HS["Existing HUTCH systems"]
        H1["Payment gateway / bank logs"]
        H2["OCS / charging"]
        H3["Product catalogue"]
        H4["DCB / VAS platform"]
        H5["Mediation CDR / PCRF"]
        H6["CRM / ticketing"]
        H7["SMSC / USSD GW / push"]
        H8["IAM / OTP / SIM registry"]
    end
    MOCK["Prototype: mock services + synthetic streams"]
    TLB -->|read| PAY & CHG & CAT & VAS & USE & CRM
    TOOLS -->|"write - idempotent"| PAY & VAS & USE & CRM
    NOTI --> NOT
    IDB --> IDA
    PAY & CHG & CAT & VAS & USE & CRM & NOT & IDA --> ESB
    ESB --> H1 & H2 & H3 & H4 & H5 & H6 & H7 & H8
    PAY & CHG & CAT & VAS & USE & CRM & NOT & IDA -.->|"prototype profile"| MOCK
```

### Diagram 8 - Security Trust Boundaries

```mermaid
flowchart LR
    subgraph Z0["Zone 0 - Internet (untrusted)"]
        CUS["Customers"]
        STF["Staff remote"]
        ATT["Threats: bots, fraud, prompt injection"]
    end
    subgraph Z1["Zone 1 - Edge"]
        WAF["WAF + rate limits"]
        COTP["Customer OTP<br/>short-lived signed tokens"]
        SSO["Staff SSO + MFA + RBAC"]
    end
    subgraph Z2["Zone 2 - HUTCH private network: Clarity"]
        APPS["Clarity services"]
        MASK["PII masking"]
        VER["Output verifier"]
        POL["Rules + policy<br/>caps · whitelists · four-eyes"]
        TOOL["Tool layer"]
        LED["Audit ledger<br/>hash-chained"]
        VAULT["Data + token vault<br/>KMS keys · expiring"]
        SLM["Self-hosted LLM"]
    end
    subgraph Z3["Zone 3 - External AI (optional)"]
        EXT["Hosted LLM<br/>masked text only · no training · no tools"]
    end
    subgraph Z4["Zone 4 - HUTCH systems of record"]
        ADP["Adapters mTLS · least privilege · read-first"]
        SOR["HUTCH systems"]
    end
    SIEM["SIEM · refund anomaly detection · TRCSL exports"]
    CUS --> WAF
    STF --> WAF
    ATT -.-> WAF
    WAF --> COTP --> APPS
    WAF --> SSO --> APPS
    APPS --> MASK --> SLM
    MASK -->|"masked only"| EXT
    SLM --> VER
    EXT --> VER
    APPS --> POL --> TOOL --> ADP --> SOR
    APPS --> VAULT
    APPS --> LED
    LED --> SIEM
    TOOL --> SIEM
```

### Diagram 9 - Deployment Architecture (Production)

```mermaid
flowchart TB
    U["Users"] --> CDN["CDN + WAF"]
    CDN --> ING["Ingress controller - TLS"]
    subgraph K8S["Kubernetes production cluster - multi-AZ / dual DC, REQUIRES HUTCH CONFIRMATION"]
        subgraph NSFE["ns: clarity-frontend"]
            FE["nextjs-web x3"]
        end
        subgraph NSAPI["ns: clarity-core"]
            API["api-gateway-bff x3"]
            ORC["orchestrator x3"]
            CASE["case-service x3"]
            TLB["timeline-builder x3"]
            RULE["rule-engine x3"]
            OPA["opa sidecars"]
            TOOLS["tool-layer x3"]
            RCPT["receipt-service x2"]
            SIGN["signing-service x2"]
        end
        subgraph NSW["ns: clarity-workers"]
            CEL["job workers - Postgres queue"]
            KC["kafka consumers"]
            REND["playwright render pool - no egress"]
            REC["reconciliation cron"]
        end
        subgraph NSAI["ns: clarity-ai"]
            AIGW["ai-gateway x2"]
            MCP["mcp-server x2"]
            PII["pii-masking x3"]
            VLLM["vLLM GPU pool - optional, HUTCH models"]
            AUT["autopsy batch"]
            FOR["foresight sandbox"]
        end
        subgraph NSINT["ns: clarity-integration"]
            ADP["adapters x2 each - egress allowlist"]
        end
        subgraph NSOBS["ns: observability"]
            OTEL["otel-collector"]
            LF["langfuse self-hosted"]
        end
    end
    subgraph DATA["Managed/HA data services"]
        PG[("PostgreSQL primary + sync replica + async DR")]
        RD[("Valkey HA")]
        KF[("Kafka 3+ brokers + Apicurio registry")]
        OBJ[("Object storage WORM")]
    end
    SEC["Secrets: OpenBao / KMS / HSM"]
    GRAF["Grafana · SIEM"]
    HUTCH["HUTCH integration boundary"]
    ING --> FE
    ING --> API
    API --> ORC --> CASE
    NSAPI --> DATA
    NSW --> DATA
    NSAI --> DATA
    ADP --> HUTCH
    K8S --> SEC
    OTEL --> GRAF
```

### Diagram 10 - CI/CD Pipeline

```mermaid
flowchart LR
    DEV["Developer"] --> PR["Pull request"]
    PR --> L["Lint + type check<br/>ruff · mypy · eslint · tsc"]
    L --> UT["Unit tests"]
    UT --> RT["Rule golden tests<br/>+ policy tests (opa test)"]
    RT --> SAST["SAST<br/>Semgrep / CodeQL"]
    SAST --> DEP["Dependency + licence scan<br/>SCA · SBOM"]
    DEP --> SEC["Secret scan"]
    SEC --> B["Build images<br/>signed (cosign)"]
    B --> CS["Container scan<br/>Trivy/Grype"]
    CS --> IT["Integration tests<br/>testcontainers + mock adapters"]
    IT --> AIE["AI eval smoke<br/>golden prompts"]
    AIE --> MERGE["Merge to main"]
    MERGE --> DDEV["Deploy DEV - GitOps"]
    DDEV --> QA["Deploy QA<br/>API · MCP · contract · E2E"]
    QA --> STG["Deploy STAGING/UAT<br/>perf · DAST · migration rehearsal"]
    STG --> UAT["UAT sign-off"]
    UAT --> CAB["Change approval / CAB"]
    CAB --> PROD["Production<br/>canary -> progressive"]
    PROD --> MON{"SLOs and refund<br/>anomaly OK?"}
    MON -- No --> RB["Automated rollback<br/>+ feature flag off"]
    MON -- Yes --> DONE["Full rollout"]
```

### Diagram 11 - Data Flow

```mermaid
flowchart LR
    subgraph SRC["Sources - HUTCH systems or mocks"]
        S1["Payment events"]
        S2["Charging events"]
        S3["Usage/FUP"]
        S4["VAS consent"]
        S5["Catalogue versions"]
        S6["Tickets / complaints"]
    end
    S1 & S2 & S3 & S4 --> KIN["Kafka ingest topics<br/>schema-validated"]
    S5 --> CATC["Catalogue cache + RAG index"]
    S6 --> COMP["complaint.created"]
    KIN --> DET["Stream detectors<br/>duplicate reload · threshold · renewal"]
    DET --> CASEQ["case.created / risk.detected"]
    API["Customer / Desk request"] --> TLB["Timeline builder<br/>on-demand reads"]
    KIN --> TLB
    TLB --> SNAP[("Evidence snapshot<br/>PostgreSQL + hash")]
    SNAP --> RULES["Rules -> decision"]
    RULES --> ACT["Actions -> adapters"]
    ACT --> LEDGER[("Action ledger + audit chain")]
    LEDGER --> RCPT["Receipts -> object storage"]
    COMP --> MASK["PII masking"] --> AUT["Autopsy -> pgvector clusters"]
    LEDGER --> CDC["Outbox / CDC"] --> WH[("Analytics warehouse<br/>masked, aggregated")]
    AUT --> WH
    WH --> FOR["Foresight seeds - aggregates only"]
    WH --> DASH["Grafana / Desk insights"]
```

### Diagram 12 - Complaint Autopsy Pipeline

```mermaid
flowchart LR
    IN["Complaints<br/>1788 notes · WhatsApp · email · app · cases"] --> DD["Dedupe<br/>exact + MinHash"]
    DD --> LID["Language detect<br/>si · ta · en · Singlish"]
    LID --> PM["PII masking<br/>Presidio + LK rules"]
    PM --> CS["LLM canonical summary<br/>English canonical form"]
    CS --> EMB["Multilingual embeddings<br/>-> pgvector"]
    EMB --> UM["UMAP reduce"]
    UM --> HD["HDBSCAN clusters<br/>+ noise"]
    HD --> JOIN["Join cluster to rule hits<br/>+ timeline facts"]
    JOIN --> LBL["LLM label + hypothesis<br/>marked unconfirmed"]
    LBL --> CXR["CX engineer review"]
    CXR -->|"known cause"| FLOW["Generate self-service flow<br/>from real read tools only"]
    CXR -->|"new cause"| RP["Draft rule proposal<br/>+ golden tests"]
    FLOW --> REP["Replay on historic cases"]
    RP --> REP
    REP --> APR["Approval: CX + product + compliance"]
    APR --> PUB["Publish behind flag<br/>WhatsApp / app"]
    PUB --> MEAS["Measure: repeats, completion"]
    MEAS --> IN
```

### Diagram 13 - Foresight Pipeline

```mermaid
flowchart LR
    SEED["Seed change<br/>new pack · price · policy · outage"] --> DIFF["Catalogue / policy diff<br/>structured parameters"]
    AGG[("Aggregated segment stats<br/>warehouse - no individual data")] --> WORLD["Build world<br/>personas: students · dual-SIM · tourists · parents"]
    HIST[("Past launches + Autopsy clusters")] --> BASE["Statistical baseline"]
    DIFF --> SIM["Swarm simulation rounds<br/>OASIS-style agents - sandbox"]
    WORLD --> SIM
    SIM --> THEMES["Predicted complaint themes<br/>by segment + uncertainty band"]
    BASE --> CAL["Calibrate + compare"]
    THEMES --> CAL
    CAL --> REV["Product + CX review<br/>advisory only"]
    REV --> MIT["Mitigations<br/>migration cards · scripts · flows · fixes"]
    MIT --> LAUNCH["Launch"]
    LAUNCH --> RADAR["Early-warning radar<br/>live spike detection on Kafka"]
    RADAR --> BT["Backtest: predicted vs actual"]
    BT --> CAL
```

### Diagram 14 - Trust Receipt Generation & Verification Flow

```mermaid
sequenceDiagram
    autonumber
    participant To as Tool Layer
    participant K as Kafka
    participant Rs as Receipt Service
    participant Sg as Signing Service (HSM/KMS)
    participant Pg as PostgreSQL ledger
    participant Rd as Render pool
    participant Ob as Object storage (WORM)
    actor Cu as Customer / TRCSL / Agent
    participant Vp as Public verify page

    To->>K: action.completed (case, actions, before/after)
    K->>Rs: consume (idempotent on action_id)
    Rs->>Rs: run recurrence check (post-action state)
    Rs->>Rs: build canonical JSON (RFC 8785)
    Rs->>Pg: read previous receipt hash (chain head, row lock)
    Rs->>Sg: sign SHA-256 of payload + prev_hash with kid
    Sg-->>Rs: Ed25519 signature
    Rs->>Pg: insert receipt + signature + chain link
    Rs->>Rd: render si/ta/en PNG/PDF + QR(verify URL)
    Rd->>Ob: store artefacts (object-lock)
    Rs->>K: receipt.issued
    Note over Rs,Ob: If signing or render fails, the action audit is already stored. Receipt retried from outbox.
    Cu->>Vp: scan QR - open /v/TR-2027-000184
    Vp->>Pg: fetch public receipt view
    Vp->>Vp: verify signature with published key (kid)
    Vp->>Vp: recompute hash, check chain link
    Vp-->>Cu: VERIFIED + masked essentials or INVALID
```

### Diagram 15 - System Context (C4 Level 1)

```mermaid
flowchart TB
    CUST["Prepaid customer<br/>smartphone · WhatsApp · basic phone"]
    GUARD["Family guardian"]
    AGENT["Support agent / supervisor"]
    FIN["Finance approver"]
    CX["CX analyst / engineer"]
    PM["Product manager"]
    COMP["Compliance officer"]
    CLARITY(["HUTCH CLARITY<br/>explain · fix by rule · prove"])
    HSYS["HUTCH systems of record<br/>charging · payments · catalogue · VAS · usage · CRM"]
    META["Meta WhatsApp Cloud API"]
    SMSC["HUTCH SMSC / USSD gateway"]
    LLMH["Hosted LLM tier - optional, masked"]
    TRCSL["TRCSL - receives regulator packs"]
    CUST --> CLARITY
    GUARD --> CLARITY
    AGENT --> CLARITY
    FIN --> CLARITY
    CX --> CLARITY
    PM --> CLARITY
    COMP --> CLARITY
    CLARITY <--> HSYS
    CLARITY <--> META
    CLARITY <--> SMSC
    CLARITY --> LLMH
    COMP --> TRCSL
```

### Diagram 16 - Container View (C4 Level 2)

```mermaid
flowchart LR
    subgraph FE["Frontends - Next.js / TS / Tailwind PWA"]
        F1["Customer Why? module<br/>web + app WebView"]
        F2["Clarity Desk"]
        F3["Ops / insights console"]
        F4["Public receipt verify page"]
    end
    subgraph SVC["Python 3.14 / FastAPI - logical services, deployed per 17 §4"]
        B1["bff-api"]
        B2["orchestrator"]
        B3["case-service"]
        B4["timeline-builder"]
        B5["rule-engine"]
        B6["decision-policy - OPA"]
        B7["tool-layer"]
        B8["receipt-service + signing"]
        B9["desk-api"]
        B10["mcp-server"]
        B11["ai-gateway"]
        B12["pii-service + token vault"]
        B13["rag-service"]
        B14["autopsy-workers"]
        B15["foresight-service"]
        B16["channel-connectors<br/>whatsapp · sms · ussd"]
        B17["adapters x N"]
        B18["reconciliation"]
    end
    subgraph ST["Stores"]
        D1[("PostgreSQL + pgvector")]
        D2[("Valkey")]
        D3[("Kafka")]
        D4[("Object storage")]
        D5[("Warehouse")]
    end
    F1 & F2 & F3 --> B1
    F4 --> B8
    B1 --> B2 & B9
    B16 --> B2
    B2 --> B3 & B11
    B3 --> B4 --> B17
    B3 --> B5 --> B6
    B3 --> B7 --> B17
    B7 --> B8
    B9 --> B6 & B7 & B3
    B11 --> B12 & B13 & B10
    B10 --> B3 & B6
    B14 --> B11
    B15 --> D5
    B18 --> B17
    SVC --- ST
```

### Diagram 17 - Clarity Core Component Design

```mermaid
flowchart TB
    subgraph CASE["Case service"]
        CS1["Case aggregate + state machine"]
        CS2["Correlation: one case across channels"]
        CS3["Outbox writer"]
    end
    subgraph TLB["Timeline builder"]
        T1["Source planner - which adapters, window"]
        T2["Parallel fetch with timeouts + circuit breakers"]
        T3["Normalizer -> TimelineEvent canonical"]
        T4["Completeness scorer per source"]
        T5["Snapshot + SHA-256 evidence hash"]
    end
    subgraph RE["Rule engine"]
        R1["Rule-pack loader - signed, versioned"]
        R2["Predicate library<br/>exists · within · count · sum · absent"]
        R3["Evaluator - all rules, deterministic order"]
        R4["Confidence scorer - evidence weights"]
        R5["Ranker + ruled-out list"]
    end
    subgraph DP["Decision policy"]
        P1["OPA bundle - versioned"]
        P2["Caps + refund budget counters"]
        P3["Risk signals: SIM swap · fraud · repeat"]
        P4["Outcome: AUTO · ONE_TAP · STAFF · EXPLAIN · HANDOFF"]
    end
    subgraph TL["Tool layer"]
        A1["Action registry + safety level"]
        A2["Confirmation / approval token check"]
        A3["Idempotency guard - Valkey + PG unique"]
        A4["Adapter command + compensation"]
        A5["Post-action verification"]
    end
    CS1 --> T1 --> T2 --> T3 --> T4 --> T5 --> R1
    R1 --> R2 --> R3 --> R4 --> R5 --> P1
    P1 --> P2 --> P3 --> P4 --> A1
    A1 --> A2 --> A3 --> A4 --> A5 --> CS3
```

### Diagram 18 - Case Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> OPEN
    OPEN --> COLLECTING_EVIDENCE
    COLLECTING_EVIDENCE --> HELD_FOR_EVIDENCE: source unavailable
    HELD_FOR_EVIDENCE --> COLLECTING_EVIDENCE: retry ok
    HELD_FOR_EVIDENCE --> HANDED_OFF: timeout
    COLLECTING_EVIDENCE --> EVALUATED
    EVALUATED --> AUTO_FIXING: AUTO
    EVALUATED --> AWAITING_CUSTOMER: ONE_TAP
    EVALUATED --> AWAITING_APPROVAL: STAFF
    EVALUATED --> EXPLAINED: EXPLAIN_ONLY
    EVALUATED --> HANDED_OFF: HANDOFF
    AWAITING_CUSTOMER --> EXECUTING: confirmed
    AWAITING_CUSTOMER --> EXPLAINED: declined or expired
    AWAITING_APPROVAL --> EXECUTING: approved
    AWAITING_APPROVAL --> EXPLAINED: rejected
    AUTO_FIXING --> EXECUTING
    EXECUTING --> ACTIONED: all actions ok
    EXECUTING --> COMPENSATING: partial failure
    COMPENSATING --> HANDED_OFF
    ACTIONED --> RECEIPTED: receipt.issued
    EXPLAINED --> RECEIPTED
    HANDED_OFF --> EVALUATED: staff re-evaluates
    RECEIPTED --> CLOSED
    CLOSED --> REOPENED: customer disputes
    REOPENED --> COLLECTING_EVIDENCE
    CLOSED --> [*]
```

### 8.1 Diagram Index (all 34 architecture diagrams in this plan)

| # | Diagram | Type | Location |
|---|---|---|---|
| 1 | High-Level Solution Architecture | flowchart | §8 |
| 2 | Detailed Enterprise Architecture | flowchart | §8 |
| 3 | Customer Dispute Request Flow | sequence | §8 |
| 4 | Decision Engine Flow | flowchart | §8 |
| 5 | AI + Deterministic Rule Boundary | flowchart | §8 |
| 6 | MCP Architecture | flowchart | §8 |
| 7 | HUTCH Integration Architecture | flowchart | §8 |
| 8 | Security Trust Boundaries | flowchart | §8 |
| 9 | Deployment Architecture (Production) | flowchart | §8 |
| 10 | CI/CD Pipeline | flowchart | §8 |
| 11 | Data Flow | flowchart | §8 |
| 12 | Complaint Autopsy Pipeline | flowchart | §8 |
| 13 | Foresight Pipeline | flowchart | §8 |
| 14 | Trust Receipt Generation & Verification | sequence | §8 |
| 15 | System Context (C4 L1) | flowchart | §8 |
| 16 | Container View (C4 L2) | flowchart | §8 |
| 17 | Clarity Core Component Design | flowchart | §8 |
| 18 | Case Lifecycle State Machine | state | §8 |
| 19 | Adapter Internal Design | flowchart | [§9.4](06-integration-tmf.md) |
| 20 | MCP Propose → Confirm → Execute | sequence | [§10.5](07-mcp.md) |
| 21 | Model Routing Tiers (token strategy) | flowchart | [§12.2](08-ai-architecture.md) |
| 22 | RAG Pipeline | flowchart | [§12.5](08-ai-architecture.md) |
| 23 | Rule Lifecycle (Teach once → publish) | flowchart | [§13.4](09-rules-decision-receipts.md) |
| 24 | Entity-Relationship Diagram | ERD | [§16.2](10-data-api-events.md) |
| 25 | Event Topology (Kafka) | flowchart | [§18.3](10-data-api-events.md) |
| 26 | PII Masking Pipeline | flowchart | [§20.1](11-security-privacy-audit.md) |
| 27 | Audit Architecture (hash chain + WORM) | flowchart | [§20.3](11-security-privacy-audit.md) |
| 28 | Network Zones | flowchart | [§22.3](12-platform-devops-testing-observability.md) |
| 29 | Environment Promotion | flowchart | [§23.1](12-platform-devops-testing-observability.md) |
| 30 | Telemetry Pipeline | flowchart | [§25.1](12-platform-devops-testing-observability.md) |
| 31 | Implementation Gantt Chart | gantt | [§28.2](13-delivery-plan.md) |
| 32 | Critical Path Network | flowchart | [§29](13-delivery-plan.md) |
| 33 | Rollout Path (Steps 1–4) | flowchart | [§34](14-risk-pilot-readiness-operations.md) |
| 34 | Degradation Ladder | flowchart | [§39](15-cost-scale-failure-kpi.md) |

When split into files ([§43](16-gap-submission-repo-docs.md)), Diagrams 1–18 go to `05-architecture-diagrams.md`. The others stay with their chapters.
---

[← 04-enterprise-architecture.md](04-enterprise-architecture.md) · [← Plan index](README.md) · [06-integration-tmf.md →](06-integration-tmf.md)
