# Product Requirements Document (PRD)
## SecureCore: AML Transaction Monitoring Simulator

### 1. Executive Summary
SecureCore is an advanced Anti-Money Laundering (AML) simulation platform designed to help financial institutions, compliance officers, and fintech startups test, validate, and optimize their transaction monitoring rules. By simulating millions of transactions and complex money laundering scenarios (e.g., structuring, layering), SecureCore allows users to assess the effectiveness of their detection logic in a risk-free sandbox environment before deploying to production.

### 2. Goals & Objectives
-   **Risk-Free Testing:** Provide a sandbox to simulate high-volume transaction data without touching production systems.
-   **Rule Optimization:** Enable users to A/B test detection rules to minimize false positives and maximize true positives.
-   **Compliance Validation:** Generate audit-ready reports demonstrating rule coverage and system performance.
-   **API-First Design:** Enable seamless integration with existing banking platforms and third-party dashboards.

### 3. Target Audience
-   **Compliance Officers:** Responsible for defining and maintaining AML rules.
-   **Data Scientists:** Building machine learning models for anomaly detection.
-   **Fintech Engineers:** Integrating transaction monitoring into banking platforms.
-   **Auditors:** Verifying the robustness of AML controls.

### 4. Key Features

#### 4.1. Data Ingestion & Management
-   **Universal Upload:** Support for CSV/Excel uploads of Transaction and Customer data.
-   **Schema Discovery:** Automatically infer data types and column mapping (schema-agnostic ingestion).
-   **Data Quality Validation:** Real-time checks for missing fields, invalid formats, and data integrity.
-   **Enterprise Connect (Roadmap):** Direct integration with PostgreSQL/Snowflake data warehouses.

#### 4.2. Advanced Rule Builder
-   **Digital Twin Logic:** Create complex detection logic (AND/OR groups, thresholds, time windows).
-   **SQL Generation:** Automatically converts abstract rules into optimized SQL queries.
-   **Scenario Library:** Pre-built templates for common typologies (e.g., "High Value Transfer", "Rapid Movement").

#### 4.3. Simulation Engine
-   **High-Performance Execution:** Process large datasets asynchronously using Celery and Redis.
-   **Scenario Injection:** capability to inject synthetic money laundering patterns (e.g., Smurfing, Round Tripping) into clean data.
-   **Versioning:** Track simulation runs over time (Baseline vs. Refined).
-   **Comparison Mode:** Side-by-side comparison of two simulation runs to visualize impact of rule changes.

#### 4.4. Analytics & Reporting
-   **Risk Overview:** High-level metrics on alert generation, risk distribution, and system health.
-   **False Positive Analysis:** Identification of noisy rules.
-   **Exportable Reports:** JSON/CSV exports of simulation results for audit trails.

### 5. Technical Architecture

#### 5.1. Backend (FastAPI)
-   **Framework:** FastAPI (Python) for high-performance REST APIs.
-   **Database:** PostgreSQL (with potential for TimescaleDB partitioning).
-   **Task Queue:** Celery + Redis for handling long-running simulations.
-   **ORM:** SQLAlchemy for database abstraction.

#### 5.2. Infrastructure & Security
-   **Authentication:** Supabase Auth (JWT) for secure user management.
-   **Deployment:** Docker containerization for easy deployment on AWS/GCP/Azure.
-   **Security:** Role-Based Access Control (RBAC) and encrypted data storage.

### 6. User Flows (API)

#### 6.1. Onboarding & Setup
1.  User authenticates via Supabase Auth (obtains JWT).
2.  User calls `GET /health` to verify system status.

#### 6.2. Simulation Loop
1.  **Ingest:** Client uploads transaction dataset via `POST /api/data/upload`.
2.  **Define:** Client creates detection configurations via `POST /api/rules`.
3.  **Simulate:** Client checks schema validity and triggers run via `POST /api/simulation/run`.
4.  **Process:** System partitions data and executes SQL logic (Async).
5.  **Review:** Client polls status and retrieves alerts via `GET /api/simulation/{run_id}/results`.

### 7. Roadmap
-   **Phase 1 (MVP):** Core Simulation Engine, CSV Ingestion, Basic API. (Completed)
-   **Phase 2:** Advanced Analytics Endpoints, Comparison Mode, Webhooks. (In Progress)
-   **Phase 3:** Enterprise Connectors, AI-based Anomaly Detection, Real-time Streaming. (Future)
