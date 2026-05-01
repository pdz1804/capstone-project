# BK-MInD Documentation Index

**Last Updated:** April 28, 2026  
**Version:** 1.0  
**Purpose:** Central navigation for all project documentation

---

## 📚 Quick Navigation by Audience

### 👨‍💼 **For Capstone Presentation / Team Leadership**
Start here for a complete overview:

1. **[README.md](../README.md)** — Project overview, architecture, scope (5-10 min read)
2. **[APPLICATION_OVERVIEW.md](technical/APPLICATION_OVERVIEW.md)** — Mission, capabilities, user workflows (10 min read)
3. **[DOCS_FEATURES.md](DOCS_FEATURES.md)** — All 18 features documented comprehensively (15 min read)
4. **[FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md](testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)** — Testing results, capacity analysis (10 min read)
5. **[AWS_Cost_Estimation_50_Users_Professional.xlsx](others/AWS_Cost_Estimation_50_Users_Professional.xlsx)** — Scalability and cost projections
6. **[SECURITY_SECTION_CAPSTONE_REPORT.md](technical/SECURITY_SECTION_CAPSTONE_REPORT.md)** — Comprehensive security architecture and implementation (15 min read) ⭐ **[USE THIS FOR REPORT]**
7. **[DOCS_TECHNICAL_GUARDRAIL_CONFIGURATION.md](technical/DOCS_TECHNICAL_GUARDRAIL_CONFIGURATION.md)** — Content safety technical details (reference)

**Time to understand full project:** ~45-60 minutes

---

### 👨‍💻 **For Developers / Backend Team**
Implementation-focused documentation:

1. **[Phase_2_FE_AI_Merge/backend/README.md](../../Phase_2_FE_AI_Merge/backend/README.md)** — Backend setup, APIs, database schema
2. **[API_REFERENCE.md](technical/API_REFERENCE.md)** — All HTTP endpoints with parameters and responses
3. **[requirements.md](requirements.md)** — Software Requirements Specification (functional, non-functional, technical)
4. **[DOCS_FEATURES.md](DOCS_FEATURES.md)** — Feature implementation details
5. **[DOCS_TECHNICAL_GUARDRAIL_CONFIGURATION.md](technical/DOCS_TECHNICAL_GUARDRAIL_CONFIGURATION.md)** — Content safety implementation
6. **[DOCS_REDIS_ASYNC_JOB_SYSTEM_GUIDE.md](technical/DOCS_REDIS_ASYNC_JOB_SYSTEM_GUIDE.md)** — Async job processing
7. **[DOCS_search-cache-redis-setup.md](technical/DOCS_search-cache-redis-setup.md)** — Search cache configuration

---

### 🎨 **For Frontend Team**
UI/UX and frontend integration:

1. **[Phase_2_FE_AI_Merge/frontend/README.md](../../Phase_2_FE_AI_Merge/frontend/README.md)** — Frontend setup, components
2. **[APPLICATION_OVERVIEW.md](technical/APPLICATION_OVERVIEW.md)** — User workflows and UX requirements
3. **[API_REFERENCE.md](technical/API_REFERENCE.md)** — API contracts to implement
4. **[DOCS_FEATURES.md](DOCS_FEATURES.md)** — Feature specifications (chat, search, insights, etc.)

---

### 🏗️ **For DevOps / Infrastructure Team**
Deployment, AWS, and infrastructure:

1. **[Phase_2_FE_AI_Merge/terraform/README.md](../../Phase_2_FE_AI_Merge/terraform/README.md)** — Terraform IaC for ECS, ALB, ECR, SageMaker
2. **[Phase_2_FE_AI_Merge/sagemaker/README.md](../../Phase_2_FE_AI_Merge/sagemaker/README.md)** — SageMaker container build and deployment
3. **[DOCS_deployment-alb-acm-custom-domain.md](technical/DOCS_deployment-alb-acm-custom-domain.md)** — HTTPS, custom domains, ACM
4. **[DOCS_TECHNICAL_WAF_CONFIGURATION.md](technical/DOCS_TECHNICAL_WAF_CONFIGURATION.md)** — AWS WAF detailed configuration, rules, capacity, operations (technical reference)
5. **[13-04-firewall-guidelines.md](technical/13-04-firewall-guidelines.md)** — WAF Terraform IaC code and state management
6. **[DOCS_search-cache-redis-setup.md](technical/DOCS_search-cache-redis-setup.md)** — Redis/ElastiCache setup
7. **[AWS_Cost_Estimation_50_Users_Professional.xlsx](others/AWS_Cost_Estimation_50_Users_Professional.xlsx)** — Cost projections and capacity planning

---

### 🧪 **For QA / Testing Team**
Testing, validation, and performance:

1. **[FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md](testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)** — Complete performance test report
2. **[README_MAIN_APIS.md](jmeter-capacity-tests/runs/README_MAIN_APIS.md)** — JMeter runbook for core APIs
3. **[README_NON_MAIN_APIS.md](jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md)** — JMeter runbook for secondary APIs
4. **[DOCS_FEATURES.md](DOCS_FEATURES.md)** — Feature acceptance criteria

---

## 🗂️ Complete Documentation Map

### 📖 Core Documentation (Root `/docs/`)

| File | Purpose | Audience | Read Time |
|------|---------|----------|-----------|
| **README.md** | Project overview, quick start, architecture summary | All | 5-10 min |
| **FEATURES.md** | All 18 features with implementation details | Developers, PM, Team | 15-20 min |
| **requirements.md** | SRS: functional, non-functional, technical requirements | PM, Team Lead | 20-30 min |
| **usecases.md** | User stories and usage scenarios | UX, PM | 10-15 min |
| **system_modeling.md** | System models, data flows, interactions | Architects | 15-20 min |
| **statistic.md** | Project statistics, metrics, coverage | Team | 5 min |

---

### 🔧 Technical Documentation (`/docs/technical/`)

| File | Purpose | Audience | Priority |
|------|---------|----------|----------|
| **API_REFERENCE.md** | HTTP endpoints, parameters, responses | Backend, Frontend devs | 🔴 High |
| **APPLICATION_OVERVIEW.md** | Architecture, capabilities, workflows, quality attributes | All | 🔴 High |
| **SECURITY_SECTION_CAPSTONE_REPORT.md** | AWS WAF + Bedrock Guardrails written for capstone report (narrative format) | Team, Leadership, Report | 🔴 High |
| **DOCS_TECHNICAL_GUARDRAIL_CONFIGURATION.md** | AWS Bedrock safety filters, PII protection, content blocking (technical details) | Security, Backend, Team | 🔴 High |
| **DOCS_TECHNICAL_WAF_CONFIGURATION.md** | AWS WAF protection pack, rules, capacity, operations (technical details) | Security, DevOps, Backend | 🟡 Medium |
| **DOCS_deployment-alb-acm-custom-domain.md** | HTTPS setup, custom domains, DNS, ACM | DevOps | 🟡 Medium |
| **DOCS_search-cache-redis-setup.md** | Redis/ElastiCache configuration, operations | DevOps, Backend | 🟡 Medium |
| **DOCS_REDIS_ASYNC_JOB_SYSTEM_GUIDE.md** | Job queue, background workers, retry logic | Backend, DevOps | 🟡 Medium |
| **DOCS_create-endpoint-script.md** | SageMaker endpoint creation automation | DevOps | 🟡 Medium |
| **14-04-2026-backend-analysis.md** | Backend performance analysis, optimization notes | Backend lead | 🟢 Low |
| **13-04-firewall-guidelines.md** | Terraform IaC for WAF deployment and state management | Security, DevOps | 🟢 Low |

---

### 📊 Testing & Performance (`/docs/testing/`)

| File | Purpose | Audience | Priority |
|------|---------|----------|----------|
| **FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md** | Complete test results, capacity analysis, recommendations | QA, PM, Team | 🔴 High |
| **README.md** | Testing overview, test categories | QA, Developers | 🟡 Medium |

---

### 📈 JMeter Test Plans (`/docs/jmeter-capacity-tests/`)

| File | Purpose | Coverage | Status |
|------|---------|----------|--------|
| **runs/README_MAIN_APIS.md** | Process, Index, Search tests with 50+ users | Core APIs | ✅ Complete |
| **runs/README_NON_MAIN_APIS.md** | Auth, Chat, Insights, Feedback tests | Secondary APIs | ✅ Complete |
| **experiments/** | Earlier experimental runs, methodology | Historical | ✓ Reference |
| **jmeter-final-correctness/** | Functional correctness tests | Validation | ✓ Reference |

---

### 🏗️ Architecture & Diagrams (`/docs/diagram/`)

| File | Purpose | Audience |
|------|---------|----------|
| **README_SYSTEM_DOCUMENTATION.md** | System documentation index, diagram links | Architects, PM |

---

### 🎓 Research Phases & History

| Folder | Focus | Key Contributions |
|--------|-------|-------------------|
| **Phase_1/** | Foundation ASR, retrieval, RAG research | BM25 vs Dense evaluation, RAG framework comparison |
| **Phase_2_FE_AI_Merge/** | **Integrated production app** | Firebase UI, Qdrant backend, S3 storage, Terraform IaC |
| **Phase_2_AI_SERVICE_FOLDER/** | Alternative AI service package | Modular architecture reference |
| **Week03-04/** | Early-stage processing, retrieval, RAG | Baseline implementations |
| **Week05-06/** | Advanced ASR, OCR, multi-model comparison | Docling, Whisper, Pyserini, Milvus |
| **Week07-09/** | Production pipeline (Stage 1-4), intelligent deduplication | **Recommended:** This is the core pipeline |

---

## 🎯 Reading Paths by Role

### 👨‍🎓 **Student / Learner (Using the Platform)**
- Start with: [APPLICATION_OVERVIEW.md](technical/APPLICATION_OVERVIEW.md) — Know what BK-MInD can do
- Then read: [DOCS_FEATURES.md](DOCS_FEATURES.md) — Understand each feature

**Time:** 20 minutes

---

### 🎯 **Product Manager**
- **Week 1:** [README.md](../README.md) → [APPLICATION_OVERVIEW.md](technical/APPLICATION_OVERVIEW.md) → [DOCS_FEATURES.md](DOCS_FEATURES.md)
- **Week 2:** [requirements.md](requirements.md) → [usecases.md](usecases.md) → [FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md](testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)
- **Week 3:** [AWS_Cost_Estimation_50_Users_Professional.xlsx](others/AWS_Cost_Estimation_50_Users_Professional.xlsx)

**Time:** 3-4 hours

---

### 👨‍💻 **Backend Developer**
1. [Phase_2_FE_AI_Merge/backend/README.md](../../Phase_2_FE_AI_Merge/backend/README.md) — Setup
2. [API_REFERENCE.md](technical/API_REFERENCE.md) — Understand endpoints
3. [requirements.md](requirements.md) — Know requirements
4. [DOCS_FEATURES.md](DOCS_FEATURES.md) — Feature implementation details
5. [GUARDRAIL_CONFIGURATION.md](technical/GUARDRAIL_CONFIGURATION.md) — Safety layer
6. Code: `Phase_2_FE_AI_Merge/backend/`

**Time:** 4-6 hours

---

### 🎨 **Frontend Developer**
1. [Phase_2_FE_AI_Merge/frontend/README.md](../../Phase_2_FE_AI_Merge/frontend/README.md) — Setup
2. [APPLICATION_OVERVIEW.md](technical/APPLICATION_OVERVIEW.md) — Workflows
3. [API_REFERENCE.md](technical/API_REFERENCE.md) — API contracts
4. [DOCS_FEATURES.md](DOCS_FEATURES.md) — What to build
5. Code: `Phase_2_FE_AI_Merge/frontend/`

**Time:** 3-4 hours

---

### 🏗️ **DevOps Engineer**
1. [Phase_2_FE_AI_Merge/terraform/README.md](../../Phase_2_FE_AI_Merge/terraform/README.md) — Infrastructure setup
2. [Phase_2_FE_AI_Merge/sagemaker/README.md](../../Phase_2_FE_AI_Merge/sagemaker/README.md) — Container & ML ops
3. [DOCS_deployment-alb-acm-custom-domain.md](technical/DOCS_deployment-alb-acm-custom-domain.md) — HTTPS/DNS
4. [DOCS_search-cache-redis-setup.md](technical/DOCS_search-cache-redis-setup.md) — Cache layer
5. [AWS_Cost_Estimation_50_Users_Professional.xlsx](others/AWS_Cost_Estimation_50_Users_Professional.xlsx) — Cost planning

**Time:** 4-5 hours

---

### 🧪 **QA / Test Engineer**
1. [FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md](testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md) — Test scope & results
2. [README_MAIN_APIS.md](jmeter-capacity-tests/runs/README_MAIN_APIS.md) — Core API testing
3. [README_NON_MAIN_APIS.md](jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md) — Full API coverage
4. [DOCS_FEATURES.md](DOCS_FEATURES.md) — Acceptance criteria
5. Jmeter files: `docs/jmeter-capacity-tests/`

**Time:** 3-4 hours

---

## 📋 Checklist for Capstone Presentation

### **Must-Have Documents** (Essential for defense)

- [ ] **[README.md](../README.md)** — Open with project overview
- [ ] **[APPLICATION_OVERVIEW.md](technical/APPLICATION_OVERVIEW.md)** — Mission, architecture, workflows
- [ ] **[DOCS_FEATURES.md](DOCS_FEATURES.md)** — Comprehensive feature list (shows scope completion)
- [ ] **[FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md](testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)** — Evidence of testing, performance
- [ ] **[GUARDRAIL_CONFIGURATION.md](technical/GUARDRAIL_CONFIGURATION.md)** — Safety measures (shows responsibility)
- [ ] **[AWS_Cost_Estimation_50_Users_Professional.xlsx](others/AWS_Cost_Estimation_50_Users_Professional.xlsx)** — Scalability projections

### **Should-Have Documents** (Supporting evidence)

- [ ] **[API_REFERENCE.md](technical/API_REFERENCE.md)** — Technical depth, API design
- [ ] **[requirements.md](requirements.md)** — SRS compliance, 37 requirements tracked
- [ ] **[usecases.md](usecases.md)** — User stories, workflows
- [ ] **Terraform / SageMaker READMEs** — Cloud-ready, production deployment

### **Nice-to-Have Documents** (Reference)

- [ ] Weekly research folder READMEs (Phase 1, Week 03-09)
- [ ] Diagram documentation
- [ ] Cost analysis

---

## 🔗 Key Links Summary

### **For Presentation Slides**

| Topic | Link | Slide Suggestion |
|-------|------|------------------|
| Project scope | [README.md](../README.md) | Intro, Overview |
| System architecture | [APPLICATION_OVERVIEW.md](technical/APPLICATION_OVERVIEW.md) | Architecture slide |
| All features | [DOCS_FEATURES.md](DOCS_FEATURES.md) | Features & capabilities |
| Performance results | [FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md](testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md) | Testing & validation |
| Scalability | [AWS_Cost_Estimation_50_Users_Professional.xlsx](others/AWS_Cost_Estimation_50_Users_Professional.xlsx) | Deployment & scalability |
| Safety | [GUARDRAIL_CONFIGURATION.md](technical/GUARDRAIL_CONFIGURATION.md) | Security & responsibility |
| API endpoints | [API_REFERENCE.md](technical/API_REFERENCE.md) | Technical depth |
| Deployment | [Phase_2_FE_AI_Merge/terraform/README.md](../../Phase_2_FE_AI_Merge/terraform/README.md) | Infrastructure |

---

## ✅ Documentation Quality Checklist

- [x] All major features documented comprehensively
- [x] API reference complete with all endpoints
- [x] Requirements traceability (37 SRS items)
- [x] Performance testing evidence
- [x] Safety/guardrail configuration documented
- [x] Architecture and workflows documented
- [x] Deployment guides (Terraform, Docker, SageMaker)
- [x] Cost estimation provided
- [x] User stories/use cases documented
- [x] All links verified and clickable

---

## 📞 Document Ownership

| Section | Owner | Last Updated |
|---------|-------|--------------|
| README, Architecture | Team Lead | April 28, 2026 |
| Features | Product/Tech | April 28, 2026 |
| API Reference | Backend Lead | April 28, 2026 |
| Testing, Performance | QA Lead | April 26, 2026 |
| Deployment, Infrastructure | DevOps Lead | April 28, 2026 |
| Guardrails, Safety | Security/Backend | April 28, 2026 |

---

**Version:** 1.0  
**Last Updated:** April 28, 2026  
**Maintenance Frequency:** Monthly
