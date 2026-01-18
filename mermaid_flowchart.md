# SAS Sandbox Simulator - System Architecture & Flow Diagrams

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph "Frontend (Next.js)"
        UI[User Interface]
        Auth[Authentication]
        Store[State Management]
    end
    
    subgraph "Backend API (FastAPI)"
        Gateway[API Gateway<br/>Rate Limiting<br/>CORS<br/>Logging]
        
        subgraph "API Endpoints"
            DataAPI[Data API<br/>/api/data]
            SimAPI[Simulation API<br/>/api/simulation]
            CompareAPI[Comparison API<br/>/api/comparison]
            RulesAPI[Rules API<br/>/api/rules]
            DashAPI[Dashboard API<br/>/api/dashboard]
        end
        
        subgraph "Core Services"
            SimService[Simulation Service]
            DataService[Data Ingestion Service]
            TTLMgr[TTL Manager]
        end
        
        subgraph "Business Logic"
            UniversalEngine[Universal Scenario Engine]
            SmartLayer[Smart Layer Processor]
            RiskEngine[Risk Engine]
            EventDetector[Event Detector]
        end
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL<br/>Transactions<br/>Customers<br/>Alerts<br/>Scenarios)]
        Redis[(Redis<br/>Cache<br/>Celery Queue)]
    end
    
    subgraph "External Services"
        Supabase[Supabase Auth]
        Prometheus[Prometheus<br/>Metrics]
    end
    
    UI --> Gateway
    Auth --> Supabase
    
    Gateway --> DataAPI
    Gateway --> SimAPI
    Gateway --> CompareAPI
    Gateway --> RulesAPI
    Gateway --> DashAPI
    
    DataAPI --> DataService
    SimAPI --> SimService
    CompareAPI --> SimService
    CompareAPI --> DB
    
    SimService --> UniversalEngine
    UniversalEngine --> SmartLayer
    SmartLayer --> EventDetector
    SmartLayer --> RiskEngine
    
    DataService --> TTLMgr
    
    SimService --> DB
    DataService --> DB
    TTLMgr --> DB
    
    SimService --> Redis
    Gateway --> Prometheus
    
    style Gateway fill:#e1f5ff
    style UniversalEngine fill:#fff4e1
    style SmartLayer fill:#ffe1e1
    style DB fill:#e1ffe1
```

## 2. Simulation Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant SimService
    participant UniversalEngine
    participant SmartLayer
    participant RiskEngine
    participant Database
    
    User->>Frontend: Configure & Start Simulation
    Frontend->>API: POST /api/simulation/run
    
    API->>API: Validate Request<br/>Check Auth<br/>Rate Limit
    
    API->>SimService: create_run()
    SimService->>Database: Create SimulationRun record
    Database-->>SimService: run_id
    
    API->>SimService: execute_run(run_id) [Background]
    
    SimService->>Database: Load Transactions & Customers
    Database-->>SimService: DataFrames
    
    SimService->>UniversalEngine: execute_scenarios()
    
    loop For Each Scenario
        UniversalEngine->>UniversalEngine: Apply Filters
        UniversalEngine->>UniversalEngine: Aggregate Transactions
        UniversalEngine->>UniversalEngine: Check Thresholds
        UniversalEngine->>UniversalEngine: Generate Alerts
    end
    
    UniversalEngine-->>SimService: Raw Alerts DataFrame
    
    SimService->>SmartLayer: apply_refinements()
    
    SmartLayer->>SmartLayer: Vectorized Keyword Filtering
    SmartLayer->>SmartLayer: Get Trigger Window Transactions
    
    loop For Each Matched Alert
        SmartLayer->>EventDetector: detect_event_context()
        EventDetector-->>SmartLayer: Context (verified, reasonable)
        SmartLayer->>SmartLayer: Decide Exclusion
        SmartLayer->>Database: Write AlertExclusionLog
    end
    
    SmartLayer-->>SimService: Refined Alerts
    
    SimService->>RiskEngine: analyze_excluded_alerts()
    RiskEngine->>Database: Get CustomerRiskProfile
    RiskEngine->>Database: Get VerifiedEntity
    RiskEngine-->>SimService: Risk Analysis
    
    SimService->>Database: Save Alerts
    SimService->>Database: Update SimulationRun (completed)
    
    SimService-->>API: Execution Complete
    API-->>Frontend: Status Update
    Frontend-->>User: Display Results
```

## 3. Data Ingestion Pipeline

```mermaid
flowchart TD
    Start([User Uploads CSV/Excel]) --> Validate{File Type<br/>Valid?}
    
    Validate -->|No| Error1[Return 400<br/>Invalid File Type]
    Validate -->|Yes| Parse[Parse File<br/>DataIngestionService]
    
    Parse --> Transform[Transform & Validate<br/>- Check required columns<br/>- Parse dates<br/>- Validate amounts]
    
    Transform --> SizeCheck{Size Within<br/>Limits?}
    
    SizeCheck -->|No| Error2[Return 413<br/>Dataset Too Large<br/>Recommend External DB]
    SizeCheck -->|Yes| CreateTTL[Create Upload Record<br/>TTLManager.create_upload_record]
    
    CreateTTL --> SetExpiry[Set expires_at<br/>Default: 48 hours]
    
    SetExpiry --> BulkInsert[Bulk Insert to Database<br/>- Add upload_id<br/>- Add expires_at]
    
    BulkInsert --> Success{Insert<br/>Successful?}
    
    Success -->|No| Rollback[Rollback Transaction<br/>Return Error]
    Success -->|Yes| Return[Return Success<br/>- upload_id<br/>- expires_at<br/>- record count]
    
    Return --> End([Upload Complete])
    
    style Start fill:#e1f5ff
    style CreateTTL fill:#fff4e1
    style BulkInsert fill:#e1ffe1
    style End fill:#e1f5ff
```

## 4. Smart Layer Processing (Vectorized)

```mermaid
flowchart TD
    Start([Receive Alerts DataFrame]) --> Init[Initialize<br/>excluded = False<br/>exclusion_reason = None]
    
    Init --> LoopRules{For Each<br/>Refinement Rule}
    
    LoopRules --> BuildKeywords[Build Keyword Pattern<br/>education: tuition, university<br/>crypto: bitcoin, binance]
    
    BuildKeywords --> VectorFilter[Vectorized Filter<br/>transactions.str.contains<br/>keyword_pattern]
    
    VectorFilter --> GetCustomers[Extract Customer IDs<br/>with Matching Transactions]
    
    GetCustomers --> FilterAlerts[Filter Alerts<br/>customer_id.isin<br/>customers_with_matches]
    
    FilterAlerts --> CheckEmpty{Matched<br/>Alerts?}
    
    CheckEmpty -->|No| NextRule[Next Rule]
    CheckEmpty -->|Yes| LoopAlerts{For Each<br/>Matched Alert}
    
    LoopAlerts --> GetWindow[Get Trigger Window<br/>Transactions<br/>alert_date - 30 days]
    
    GetWindow --> CheckTxns{Transactions<br/>in Window?}
    
    CheckTxns -->|No| NextAlert[Next Alert]
    CheckTxns -->|Yes| DetectContext[EventDetector<br/>detect_event_context]
    
    DetectContext --> Verified{Is Verified &<br/>Amount Reasonable?}
    
    Verified -->|No| NextAlert
    Verified -->|Yes| Exclude[Mark as Excluded<br/>Set exclusion_reason]
    
    Exclude --> LogExclusion[Write AlertExclusionLog<br/>- alert_id<br/>- rule_id<br/>- reason<br/>- risk_flags]
    
    LogExclusion --> NextAlert
    NextAlert --> LoopAlerts
    
    LoopAlerts -->|Done| NextRule
    NextRule --> LoopRules
    
    LoopRules -->|Done| Return([Return Refined<br/>Alerts DataFrame])
    
    style Start fill:#e1f5ff
    style VectorFilter fill:#ffe1e1
    style DetectContext fill:#fff4e1
    style LogExclusion fill:#e1ffe1
    style Return fill:#e1f5ff
```

## 5. API Request Flow with Security

```mermaid
sequenceDiagram
    participant Client
    participant RateLimiter
    participant CORS
    participant Auth
    participant Logging
    participant Endpoint
    participant Database
    participant Prometheus
    
    Client->>RateLimiter: HTTP Request
    
    RateLimiter->>RateLimiter: Check IP Rate<br/>(200/min)
    
    alt Rate Limit Exceeded
        RateLimiter-->>Client: 429 Too Many Requests
    else Within Limit
        RateLimiter->>CORS: Forward Request
        
        CORS->>CORS: Validate Origin<br/>Check ALLOWED_ORIGINS
        
        alt Invalid Origin
            CORS-->>Client: 403 Forbidden
        else Valid Origin
            CORS->>Auth: Forward Request
            
            Auth->>Auth: Validate JWT Token<br/>(Supabase)
            
            alt Invalid/Missing Token
                Auth-->>Client: 401 Unauthorized
            else Valid Token
                Auth->>Logging: Forward Request
                
                Logging->>Logging: Start Timer<br/>Log Request Details
                
                Logging->>Endpoint: Execute Handler
                
                Endpoint->>Database: Query/Update Data
                Database-->>Endpoint: Result
                
                alt Success
                    Endpoint-->>Logging: 200 Response
                else Error
                    Endpoint-->>Logging: 4xx/5xx Response
                end
                
                Logging->>Logging: Calculate Duration<br/>Log Response
                
                Logging-->>Client: HTTP Response
            end
        end
    end
```

## 6. Database Schema Relationships

```mermaid
erDiagram
    SIMULATION_RUN ||--o{ ALERT : generates
    SIMULATION_RUN {
        string run_id PK
        string run_type
        datetime created_at
        int total_alerts
        int total_transactions
        string status
    }
    
    ALERT ||--o| ALERT_EXCLUSION_LOG : has
    ALERT {
        string alert_id PK
        string run_id FK
        string scenario_id FK
        string customer_id FK
        datetime alert_date
        float risk_score
        string risk_classification
        string alert_status
        boolean excluded
        string exclusion_reason
    }
    
    ALERT_EXCLUSION_LOG {
        string log_id PK
        string alert_id FK
        datetime exclusion_timestamp
        string rule_id
        string exclusion_reason
        json risk_flags
    }
    
    CUSTOMER ||--o{ TRANSACTION : makes
    CUSTOMER ||--o| CUSTOMER_RISK_PROFILE : has
    CUSTOMER {
        string customer_id PK
        string customer_name
        string customer_type
        string upload_id FK
        datetime expires_at
    }
    
    TRANSACTION {
        string transaction_id PK
        string customer_id FK
        datetime transaction_date
        float transaction_amount
        string transaction_narrative
        string beneficiary_name
        string upload_id FK
        datetime expires_at
    }
    
    CUSTOMER_RISK_PROFILE {
        string profile_id PK
        string customer_id FK
        boolean is_pep
        boolean has_adverse_media
        boolean high_risk_occupation
        int previous_sar_count
    }
    
    VERIFIED_ENTITY {
        string entity_id PK
        string entity_name
        string entity_type
        boolean is_active
    }
    
    DATA_UPLOADS {
        string upload_id PK
        string user_id
        string filename
        int record_count_transactions
        int record_count_customers
        json schema_snapshot
        datetime expires_at
        string status
    }
    
    SCENARIO_CONFIG {
        string scenario_id PK
        string scenario_name
        string user_id
        json config_json
        json field_mappings
        boolean enabled
    }
```

## 7. TTL Management Flow

```mermaid
stateDiagram-v2
    [*] --> DataUploaded: User uploads CSV
    
    DataUploaded --> Active: TTLManager creates record<br/>expires_at = now + 48h
    
    Active --> Extended: User clicks "Extend +24h"<br/>TTLManager.extend_ttl()
    
    Extended --> Active: New expires_at set<br/>(max 168h from now)
    
    Active --> Warning: expires_at < 6 hours<br/>UI shows warning
    
    Warning --> Extended: User extends
    Warning --> Expired: Time runs out
    
    Active --> Expired: expires_at reached<br/>TTLManager.cleanup_expired()
    
    Expired --> Deleted: Records removed<br/>from database
    
    Deleted --> [*]
    
    note right of Active
        Status: active
        Data accessible
        Simulations can run
    end note
    
    note right of Expired
        Status: expired
        Data deleted
        Upload record archived
    end note
```

## 8. Logic Comparison & Gap Analysis Workflow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant CompareService
    participant SimService
    participant Database

    User->>Frontend: Select Rule A & Rule B
    
    alt Missing Simulation Data
        Frontend->>User: Show "Simulate Now" Prompt
        User->>Frontend: Confirm Simulation
        Frontend->>API: POST /api/simulation/run
        API->>SimService: execute_run()
        SimService-->>API: Success
        API-->>Frontend: Run Complete
    end

    User->>Frontend: Click "Compare Logic"
    Frontend->>API: POST /api/comparison/compare (scenario_ids)
    
    API->>API: Resolve Scenario IDs to Latest Run IDs
    
    API->>CompareService: compare_runs(baseline_id, refined_id)
    
    CompareService->>Database: Load Alerts for Run A (Baseline)
    CompareService->>Database: Load Alerts for Run B (Refined)
    
    CompareService->>CompareService: Identify Common Alerts (Matches)
    CompareService->>CompareService: Identify Suppressed Alerts (Gaps)
    
    CompareService->>API: Result Metrics & Risk Analysis
    API-->>Frontend: Display Diff Dashboard
    Frontend-->>User: Show Efficiency vs Effectiveness
```

## Legend

- **Blue boxes**: Entry/Exit points
- **Yellow boxes**: Processing/Computation
- **Red boxes**: Critical operations (filtering, exclusion, comparisons)
- **Green boxes**: Database operations
- **Diamond shapes**: Decision points
