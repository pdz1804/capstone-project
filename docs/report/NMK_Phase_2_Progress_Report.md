# Phase 2 Progress Report: Requirements Engineering, Use Case Analysis, and Project Documentation

**Reporting Period:** January 2026 - March 2026
**Subject:** Capstone Thesis - BK-MInD: AI-Powered Lecture Learning System
**Phase:** Phase 2 - Requirements Specification, Use Case Development, and System Architecture

---

## Overview

This report documents comprehensive requirements engineering and system design work completed during Phase 2 of capstone thesis project. The primary objective of Phase 2 was to establish a complete foundation of system specifications, use case documentation, and architectural planning that would guide implementation stages. While Phase 1 focused on initial research and prototyping, Phase 2 required systematic analysis of user needs, detailed functional requirements specification, and comprehensive use case development that would serve as the blueprint for subsequent development phases.

Four major workstreams were executed in parallel during this phase. The first workstream involved comprehensive requirements engineering, translating stakeholder needs into 35 detailed requirements across functional, non-functional, and technical categories. The second workstream focused on use case development, creating 10 detailed use cases with scenarios, activity diagrams, and integration matrices that document all user interactions with the system. The third workstream addressed project statistics and analysis, providing quantitative insights into requirements distribution, AI vs software component balance, and implementation priorities. The fourth workstream involved system architecture documentation, creating detailed technical specifications and integration patterns that would guide the development team.

Each section below describes what was analyzed, reasoning behind key decisions, technical depth of specification, and current status of each workstream.

---

## 1. Comprehensive Requirements Engineering and Analysis

### 1.1 Motivation and Background

One of the critical success factors for this capstone project is establishing clear, comprehensive, and implementable requirements that serve as the foundation for all subsequent development work. In Phase 1, the team conducted initial research and identified high-level system capabilities, but there was no systematic requirements engineering process that would translate these concepts into detailed, testable, and prioritized specifications.

Phase 2 therefore required a rigorous requirements engineering process with the following design criteria: requirements must be complete and unambiguous, covering all aspects of system functionality; requirements must be categorized and prioritized to guide implementation sequencing; requirements must be traceable from user needs through to technical implementation; and requirements must be verifiable with clear acceptance criteria. This systematic approach ensures that development team has clear guidance and that stakeholders can validate that delivered system meets their expectations.

### 1.2 Requirements Architecture: Three-Tier Specification Framework

The requirements were organized into three distinct tiers, each serving a different purpose in the engineering process. This three-tier approach ensures comprehensive coverage while maintaining clear separation of concerns.

**Tier 1 - Functional Requirements (20 Requirements)**

Functional requirements define what the system must do from a user perspective. These requirements were derived from detailed analysis of educational workflows, student needs, and instructor expectations. The functional requirements are organized into six logical categories that map directly to system capabilities:

Content Processing requirements (8) cover the core data ingestion capabilities including audio extraction from video files using MoviePy, document processing with OCR using Tesseract, image processing with vision-language models, and advanced spreadsheet parsing with merged cell support. These requirements establish the foundation for processing heterogeneous educational materials into a unified knowledge base.

Information Retrieval requirements (3) address the search and discovery capabilities including BM25 sparse retrieval for exact keyword matching, dense semantic retrieval using sentence transformers, and hybrid retrieval combining both approaches. These requirements ensure that students can find relevant content using both precise terminology and conceptual queries.

Question Answering requirements (2) cover the intelligent response generation including LLM-powered answer generation with proper citations and result presentation with relevance scoring and filtering. These requirements ensure that the system provides not just raw content but intelligent, contextual responses to student queries.

User Interface requirements (2) address the human-computer interaction including drag-and-drop file upload interface and natural language search interface with result refinement capabilities. These requirements ensure that the system is accessible and usable for students with varying technical proficiency.

Lecture Summary requirements (2) cover automated content summarization including multi-level summary generation with customizable length and interactive summary navigation with timestamp linking. These requirements provide value-added features that help students quickly review lecture content.

Personalization requirements (3) address adaptive learning capabilities including personalized learning path generation, adaptive assessment creation, and performance analytics dashboard. These requirements differentiate the system from basic content retrieval systems by providing personalized educational experiences.

**Tier 2 - Non-Functional Requirements (8 Requirements)**

Non-functional requirements define how the system must perform rather than what it must do. These requirements are critical for ensuring system reliability, performance, and user satisfaction. They are organized into four categories:

Performance requirements (2) establish quantitative targets including sub-second response times for text retrieval, two-second response times for visual queries, ten-second response times for answer generation, and support for 10,000+ documents with 10+ concurrent users. These requirements ensure that the system can handle realistic educational workloads.

Reliability requirements (2) focus on system availability and data integrity including 99% uptime during business hours, graceful error handling and recovery, automatic retry mechanisms, and comprehensive backup and recovery procedures. These requirements ensure that students can rely on the system for their learning activities.

Usability requirements (2) address user experience quality including intuitive web interface requiring minimal training, responsive design for desktop and mobile, clear error messages and guidance, and accessibility support including screen readers and keyboard navigation. These requirements ensure that the system is inclusive and easy to use.

Security requirements (2) cover data protection and privacy including secure file upload with validation, API key management for external services, user authentication and authorization, data encryption in transit and at rest, and privacy compliance with educational data regulations. These requirements protect student data and ensure institutional compliance.

**Tier 3 - Technical Requirements (7 Requirements)**

Technical requirements define the implementation constraints and technology choices. These requirements provide specific guidance for development team while ensuring consistency across system components. They are organized into three categories:

System Architecture requirements (3) specify the core technology stack including Python 3.9+ runtime with FastAPI framework, React 18+ frontend with Vite build system, and vector database combined with traditional document store. These requirements establish the technical foundation for the system.

Integration requirements (2) address external service dependencies including OpenAI API for GPT models, Google Gemini API for multimodal processing, Hugging Face for model hosting, and cloud storage for file backup. These requirements ensure that the system can leverage best-in-class AI services while maintaining flexibility.

Deployment requirements (2) cover production deployment including Docker support for consistent deployment, Docker Compose for multi-service orchestration, environment-specific configurations, health check endpoints, and support for cloud deployment on AWS, GCP, or Azure. These requirements ensure that the system can be reliably deployed and maintained in production environments.

### 1.3 Requirements Prioritization and Risk Assessment

Each requirement was assigned a priority level based on business impact, technical complexity, and dependency relationships. Critical priority requirements (5) must be implemented in Phase 1 as they form the foundation for all other functionality. Essential priority requirements (15) should be implemented in Phase 2 to provide core value to users. Enhanced priority requirements (10) can be implemented in Phase 3 to improve user experience. Administrative priority requirements (5) can be implemented in Phase 4 to support system maintenance.

Risk assessment identified highest-risk requirements including image processing with vision-language models, visual retrieval with late-interaction embeddings, learning path generation with recommendation algorithms, adaptive assessment with question generation, and scalability requirements for large-scale deployment. Mitigation strategies include prototyping, incremental development, and performance testing.

### 1.4 Requirements Traceability Matrix

A comprehensive traceability matrix was established linking each requirement to its originating stakeholder need, associated use cases, implementation components, and verification criteria. This matrix ensures that every requirement can be traced from business need through to technical implementation and testing. The traceability matrix includes 35 requirements mapped to 10 use cases and 7 system modules, providing complete coverage analysis.

---

## 2. Use Case Development and Scenario Analysis

### 2.1 Motivation and Background

Use cases serve as the bridge between abstract requirements and concrete implementation by describing how different actors will interact with the system to achieve their goals. While requirements define what the system must do, use cases provide detailed narratives of user interactions, including main success paths, alternative flows, and exception handling. Phase 2 required developing comprehensive use cases that would guide UI design, API development, and testing scenarios.

The use case development process followed a systematic approach: actor identification to define all user roles and their goals; scenario development to create detailed interaction flows; workflow modeling to visualize processes and identify dependencies; integration analysis to understand cross-use case relationships; and validation to ensure completeness and consistency with requirements.

### 2.2 Use Case Architecture: Core and Extended Features

Ten comprehensive use cases were developed, organized into two logical groups that reflect the system's evolution from basic functionality to advanced learning features.

**Core RAG System Use Cases (4)**

UC-001: Upload and Process Educational Content represents the foundational content ingestion workflow. This use case documents how students and instructors upload lecture materials in various formats (video, audio, documents, images) and how the system processes them through normalization, transcription, and indexing stages. The use case includes detailed scenarios for successful processing, error handling for unsupported formats, and progress tracking for long-running jobs.

UC-002: Search Educational Content covers the primary user interaction pattern. This use case documents how students formulate natural language queries, how the system performs hybrid retrieval across text and visual content, and how results are ranked and presented. Scenarios include simple keyword searches, complex conceptual queries, and multi-modal queries combining text and image input.

UC-003: Generate Answer with Citations represents the core value proposition. This use case documents how the system assembles relevant context from retrieved chunks, generates intelligent responses using LLMs, and provides proper citations back to source materials. Scenarios cover factual questions, conceptual explanations, and step-by-step problem solving.

UC-004: Manage Processing Pipeline addresses administrative functionality. This use case documents how system administrators monitor processing jobs, manage system resources, view performance metrics, and handle error conditions. Scenarios include job monitoring, resource scaling, and system maintenance.

**Extended Learning Features Use Cases (6)**

UC-005: Generate Automated Lecture Summary provides value-added content processing. This use case documents how students request system-generated summaries of processed lectures, with options for brief (2-3 minute), standard (5-7 minute), or comprehensive (10-15 minute) summaries. The use case includes detailed scenarios for summary customization, timestamp linking, and export functionality.

UC-006: Navigate and Interact with Summary covers summary exploration. This use case documents how students interact with generated summaries through clickable sections, timeline navigation, search within summaries, and annotation capabilities. Scenarios include lecture review, exam preparation, and collaborative note-taking.

UC-007: Create Custom Summary with Focus Areas addresses personalization needs. This use case documents how students can request summaries focused on specific topics, difficulty levels, or learning objectives. Scenarios include targeted review, prerequisite learning, and assessment preparation.

UC-008: Generate Personalized Learning Path represents adaptive learning functionality. This use case documents how the system analyzes student performance data, identifies knowledge gaps, and creates customized learning roadmaps. Scenarios include remedial learning, advanced topic exploration, and skill progression planning.

UC-009: Take Adaptive Assessment and Receive Recommendations covers evaluation capabilities. This use case documents how the system generates adaptive questions that adjust difficulty based on student responses, provides immediate feedback, and suggests next learning steps. Scenarios include formative assessment, summative evaluation, and diagnostic testing.

UC-010: View Learning Dashboard and Progress Analytics provides learning analytics. This use case documents how students and instructors view performance metrics, learning progress, strength/weakness analysis, and engagement patterns. Scenarios include progress monitoring, performance review, and learning strategy adjustment.

### 2.3 Activity Diagrams and Workflow Visualization

For each use case, detailed activity diagrams were created using Mermaid syntax to visualize workflows. These diagrams show the sequence of actions, decision points, and system responses for each scenario. The activity diagrams serve multiple purposes: they provide clear visual documentation for developers, they identify integration points between system components, and they serve as the basis for user interface design.

Key activity diagrams include the Lecture Summary Generation Workflow showing the seven-step process from user request through summary delivery; the Personalized Learning Path Generation Workflow illustrating the five-stage process from data collection through path presentation; the Adaptive Assessment Workflow documenting the question-answer-feedback loop; and the Learning Dashboard Interaction Workflow showing the data visualization and user interaction patterns.

### 2.4 Use Case Integration and Dependency Analysis

A comprehensive use case integration matrix was developed showing relationships between use cases, shared components, and implementation dependencies. This analysis revealed that core use cases (UC-001 through UC-004) must be implemented first as they provide the foundation for extended features. Extended use cases (UC-005 through UC-010) depend on core functionality but can be implemented in parallel once foundation is established.

The integration analysis also identified shared components across use cases, including user authentication, file management, search interface, and notification services. This component-level analysis helps optimize development effort by identifying reusable functionality that can serve multiple use cases.

---

## 3. Project Statistics and Resource Allocation Analysis

### 3.1 Motivation and Background

Quantitative analysis of project scope and resource requirements is essential for effective project planning and management. Phase 2 required developing comprehensive statistics that would provide objective measures of project complexity, resource needs, and implementation priorities. These statistics serve multiple purposes: they provide realistic effort estimates for planning, they help balance AI and software engineering resources, and they support data-driven decision making for implementation sequencing.

### 3.2 Statistical Analysis Framework

The statistical analysis was organized around four key dimensions: requirements distribution, complexity assessment, AI vs software balance, and resource allocation planning.

**Requirements Distribution Analysis**

Out of 35 total requirements, 20 are functional (57%), 8 are non-functional (23%), and 7 are technical (20%). This distribution indicates a strong focus on user-facing functionality while maintaining adequate attention to system quality and technical implementation. The functional requirements are further distributed across six categories, with content processing (40% of functional) and personalization (15% of functional) representing the largest areas of focus.

**Use Case Complexity Analysis**

The 10 use cases were classified by complexity based on technical difficulty, integration requirements, and dependency relationships. High complexity use cases (4) include those involving AI model integration and complex data processing: UC-003 (Answer Generation), UC-005 (Summary Generation), UC-008 (Learning Path Generation), and UC-009 (Adaptive Assessment). Medium complexity use cases (5) involve significant user interaction and system coordination: UC-001 (Content Processing), UC-002 (Search), UC-006 (Summary Navigation), UC-007 (Custom Summary), and UC-010 (Dashboard). Low complexity use cases (1) are primarily administrative: UC-004 (Pipeline Management).

**AI vs Software Requirements Balance**

A critical analysis was the balance between AI-heavy and software-heavy requirements. AI-heavy requirements (12, 34%) include those primarily dependent on machine learning models, natural language processing, or computer vision. Software-heavy requirements (23, 66%) include those focused on traditional software engineering, system architecture, and user interface development. This 34/66 split represents a balanced approach that ensures both AI innovation and engineering reliability.

**Resource Allocation Planning**

Based on the requirements analysis, development effort was allocated across four areas: AI development (40% of effort) for the 12 AI-heavy requirements; software engineering (35% of effort) for the 23 software-heavy requirements; frontend development (15% of effort) for user interface and user experience; and testing & quality assurance (10% of effort) for system validation and reliability.

### 3.3 Implementation Priority Matrix

The requirements and use cases were mapped to three implementation stages based on dependency analysis and value delivery.

**Stage 1 (MVP)** includes 15 functional requirements covering core RAG functionality: content processing, basic search, and answer generation. This stage delivers the minimum viable product that provides core value to students.

**Stage 2 (Learning Enhancement)** includes 2 functional requirements for lecture summary features: automated summary generation and interactive navigation. This stage adds significant educational value beyond basic content retrieval.

**Stage 3 (Personalization)** includes 3 functional requirements for adaptive learning features: personalized learning paths, adaptive assessment, and analytics dashboard. This stage provides the full educational experience.

### 3.4 Success Metrics and Quality Targets

Specific success metrics were established for each implementation stage. Stage 1 success is measured by processing accuracy (ASR WER < 15%, OCR accuracy > 90%), retrieval relevance (nDCG@10 > 0.2), and system performance (sub-second response times). Stage 2 success adds summary quality metrics (concept coverage > 85%, user satisfaction > 4.2/5.0). Stage 3 success includes learning outcome metrics (grade improvement > 15%, engagement > 80%).

---

## 4. System Architecture Documentation and Technical Specifications

### 4.1 Motivation and Background

System architecture documentation serves as the technical blueprint that guides implementation teams and ensures consistency across system components. Phase 2 required creating comprehensive architecture specifications that would address both logical software design and physical deployment considerations. The architecture documentation needed to be detailed enough to guide development while remaining flexible enough to accommodate technology choices and implementation discoveries.

The architecture documentation process addressed multiple perspectives: logical component organization showing how modules interact; data flow documentation showing how information moves through the system; integration patterns defining how external services are consumed; and scalability considerations ensuring the system can handle growth in users and content.

### 4.2 Modular Architecture Design

The system was designed with seven distinct modules, each with clear responsibilities and well-defined interfaces. This modular approach provides several benefits: parallel development by different team members, independent testing and deployment of components, clear separation of concerns for maintainability, and flexibility for technology choices within modules.

**Content Processing Module** handles all data ingestion and transformation. This module includes components for audio extraction, speech recognition, document processing, image analysis, and spreadsheet parsing. It's designed as high-complexity, critical-priority module that forms the foundation for all other system capabilities.

**Information Retrieval Module** manages search and discovery functionality. This module includes sparse retrieval (BM25), dense retrieval (embeddings), and hybrid retrieval combining both approaches. It's designed as high-complexity, critical-priority module that enables core user interactions.

**Question Answering Module** generates intelligent responses to user queries. This module includes context assembly, LLM integration, and answer formatting with citations. It's designed as medium-complexity, critical-priority module that provides the system's primary value proposition.

**User Interface Module** handles all user interactions and presentation. This module includes file upload interface, search interface, result display, and user navigation. It's designed as medium-complexity, high-priority module that ensures system usability.

**Lecture Summary Module** provides automated content summarization. This module includes summary generation, customization options, and interactive navigation. It's designed as high-complexity, high-priority module that adds significant educational value.

**Personalization Module** delivers adaptive learning features. This module includes learning path generation, adaptive assessment, and performance analytics. It's designed as very high-complexity, high-priority module that differentiates the system from basic retrieval systems.

**System Administration Module** provides operational and maintenance capabilities. This module includes system monitoring, resource management, and administrative interfaces. It's designed as medium-complexity, medium-priority module that ensures system reliability.

### 4.3 Technology Stack Specification

Detailed technology specifications were created for each system component, providing clear guidance for implementation teams.

**AI/ML Technology Stack** specifies the artificial intelligence and machine learning components: PyTorch for deep learning models, Transformers for natural language processing, LangChain for LLM orchestration, Whisper for speech recognition, sentence-transformers for embeddings, and ColQwen for visual-language understanding.

**Backend Technology Stack** defines the server-side infrastructure: FastAPI for REST API framework, Python 3.9+ runtime environment, async processing for performance, SQLAlchemy for database ORM, and Redis for caching and session management.

**Frontend Technology Stack** specifies the client-side technologies: React 18+ with modern hooks for user interface, Vite for build system and development server, TailwindCSS for styling and responsive design, and modern state management for application state.

**Database and Storage Stack** covers data persistence: Vector database for semantic search capabilities, traditional document store for structured data, cloud storage for file backups, and caching layer for performance optimization.

**Deployment and Infrastructure Stack** defines the production environment: Docker for containerization, Docker Compose for service orchestration, cloud deployment support (AWS/GCP/Azure), and monitoring/logging infrastructure for operational visibility.

### 4.4 Integration Patterns and External Dependencies

The system architecture defines clear patterns for integrating with external services and APIs. These patterns ensure consistent, reliable, and maintainable integrations.

**AI Service Integration Pattern** defines how external AI services are consumed: API key management through environment variables, retry mechanisms for failed requests, rate limiting for cost control, fallback strategies for service unavailability, and response caching to minimize API calls.

**Data Processing Pipeline Pattern** specifies how data flows through processing stages: event-driven architecture for job triggering, message queues for asynchronous processing, state management for long-running jobs, and error handling and recovery mechanisms.

**User Interface Integration Pattern** defines how frontend communicates with backend: RESTful API design with clear endpoints, WebSocket connections for real-time updates, authentication and authorization patterns, and error handling and user feedback mechanisms.

---

## Current Status and Implementation Readiness

### 5.1 Documentation Completeness

All four major workstreams have been completed successfully. The requirements engineering workstream produced 35 comprehensive requirements with full traceability and verification criteria. The use case development workstream delivered 10 detailed use cases with scenarios, activity diagrams, and integration analysis. The project statistics workstream provided quantitative analysis and resource allocation planning. The system architecture workstream created detailed technical specifications and integration patterns.

### 5.2 Implementation Readiness Assessment

The project is now fully ready for implementation Phase 1. All requirements are specified, prioritized, and linked to use cases. All use cases are documented with detailed scenarios and workflow visualizations. The system architecture provides clear technical guidance for development teams. Resource allocation and implementation sequencing are established based on dependency analysis and value delivery.

### 5.3 Quality Assurance and Validation

Multiple quality assurance measures have been implemented throughout Phase 2. Requirements validation ensured stakeholder alignment and completeness. Use case validation verified that all user interactions are covered and workflows are logical. Architecture validation confirmed that technical specifications are feasible and consistent. Cross-document validation ensured traceability and consistency across all deliverables.

### 5.4 Next Steps and Transition Plan

Phase 2 has established a solid foundation for implementation. The immediate next steps include: setting up development environment with specified technology stack, implementing core modules following the modular architecture, establishing CI/CD pipeline for automated testing and deployment, and beginning user acceptance testing with stakeholders.

The comprehensive documentation created during Phase 2 provides clear guidance for implementation teams, ensures alignment between requirements and delivered functionality, and establishes quality criteria for validation. The project is well-positioned for successful implementation and delivery of a high-quality educational content processing system.