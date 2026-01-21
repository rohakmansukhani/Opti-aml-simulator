# Product Requirements Document (PRD)
## SecureCore: AML Transaction Monitoring Simulator

### 1. Executive Summary
SecureCore is an advanced Anti-Money Laundering (AML) simulation platform designed to help financial institutions, compliance officers, and fintech startups test, validate, and optimize their transaction monitoring rules. By simulating millions of transactions and complex money laundering scenarios (e.g., structuring, layering), SecureCore allows users to assess the effectiveness of their detection logic in a risk-free sandbox environment before deploying to production.

### 2. Goals & Objectives
-   **Risk-Free Testing:** Provide a sandbox to simulate high-volume transaction data without touching production systems.
-   **Rule Optimization:** Enable users to A/B test detection rules to minimize false positives and maximize true positives.
-   **Compliance Validation:** Generate audit-ready reports demonstrating rule coverage and system performance.

### 3. Target Audience
-   **Compliance Officers:** Responsible for defining and maintaining AML rules.
-   **Fintech Engineers:** Integrating transaction monitoring into banking platforms.
-   **Auditors:** Verifying the robustness of AML rules.

### 4. Key Features

#### 4.1. Data Ingestion & Management
-   **Universal Upload:** Support for CSV/Excel uploads of Transaction and Customer data.
-   **Schema Discovery:** Automatically infer data types and column mapping (schema-agnostic ingestion).
-   **Data Quality Validation:** Real-time checks for missing fields, invalid formats, and data integrity.
-   **Enterprise Connect (Roadmap):** Direct integration with PostgreSQL data warehouses.

#### 4.2. Advanced Rule Builder
-   **Visual Editor:** No-code interface for creating complex logic (AND/OR groups, thresholds, time windows).
-   **SQL Generation:** Automatically converts visual rules into optimized SQL queries.
-   **Scenario Library:** Pre-built templates for common typologies (e.g., "High Value Transfer", "Rapid Movement").
-   **Live Preview:** meaningful feedback on how many transactions a rule would flag.

#### 4.3. Simulation Engine
-   **High-Performance Execution:** Process large datasets asynchronously using Celery and Redis.
-   **Scenario Injection:** capability to inject synthetic money laundering patterns (e.g., Smurfing, Round Tripping) into clean data.
-   **Versioning:** Track simulation runs over time (Baseline vs. Refined).
-   **Comparison Mode:** Side-by-side comparison of two simulation runs to visualize impact of rule changes.

#### 4.4. Analytics Dashboard
-   **Risk Overview:** High-level metrics on alert generation, risk distribution, and system health.
-   **False Positive Analysis:** Tools to identify and tune noisy rules.
-   **Exportable Reports:** PDF/CSV exports of simulation results for audit trails.

### 5. Technical Architecture

#### 5.1. Backend (FastAPI)
-   **Framework:** FastAPI (Python) for high-performance REST APIs.
-   **Database:** PostgreSQL (with potential for TimescaleDB partitioning).
-   **Task Queue:** Celery + Redis for handling long-running simulations.
-   **ORM:** SQLAlchemy for database abstraction.


#### 5.3. Infrastructure & Security
-   **Authentication:** Supabase Auth (JWT) for secure user management.
-   **Deployment:** Docker containerization for easy deployment on AWS/GCP/Azure.
-   **Security:** Role-Based Access Control (RBAC) and encrypted data storage.

### 6. User Flows

#### 6.1. Onboarding & Setup
1.  User signs up via Supabase Auth.
2.  User completes email verification.
3.  User lands on "Initialize Sandbox" to upload data or connect DB.

#### 6.2. Simulation Loop
1.  **Ingest:** Upload generic transaction dataset.
2.  **Define:** Create or select detection scenarios (e.g., "Transactions > $10k").
3.  **Simulate:** Run the engine. The system partitions data and executes SQL logic.
4.  **Review:** Analyze generated alerts on the Dashboard.
5.  **Refine:** Tweak rule parameters and re-run to compare results.

