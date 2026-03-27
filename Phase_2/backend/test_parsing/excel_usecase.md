# Stakeholder-Oriented Use Cases for an Excel Parsing Feature

## 1. Scope Clarification

This section rewrites the stakeholder-oriented use cases for an Excel parsing feature using a cleaner taxonomy. The target stakeholder groups are **Business Analyst (BA), Data Analyst (DA), Project Manager (PM), Human Resources (HR), Accountant**, and a more cautious **Computer Science (CS) / technical student** category. In this version, **UAT/QA is not treated as a primary stakeholder group**, because it was not part of the original user list. UAT- and QA-related spreadsheets may still appear in practice, but they should be considered adjacent artifacts rather than a replacement for BA-oriented work.

## 2. Role of the Excel Parsing Feature

The purpose of the Excel parsing feature is to convert spreadsheet workbooks into structured, machine-readable representations while preserving the information that gives the workbook meaning: sheet boundaries, logical tables, formulas, headers, merged cells, comments, visual summaries, and cross-sheet relationships. This matters because Excel is often used not just as a raw data container but also as a lightweight planning, reporting, and decision-support environment. Microsoft’s own guidance on PivotTables, PivotCharts, and dashboard construction makes that point rather loudly in spreadsheet dialect.

## 3. Stakeholder-Specific Use Cases and Corresponding Excel File Features

### 3.1 Business Analyst (BA)

**Use case.**  
A business analyst uses Excel to organize and communicate business analysis artifacts such as stakeholder lists, prioritization matrices, requirement mappings, process-related inventories, RACI-style responsibility views, and traceability-oriented records. IIBA defines business analysis as enabling change by defining needs and recommending solutions that deliver value, and its materials emphasize stakeholder lists, requirement traceability, prioritization, and maintaining relationships between business needs and solution elements.

**Typical Excel file features.**  
BA-oriented workbooks are usually **text-heavy rather than number-heavy**. They often contain multiple worksheets, structured identifiers such as requirement IDs or stakeholder IDs, ownership columns, priority/status columns, business-rule notes, dependency references, and sectioned matrices. Compared with analyst or finance files, BA workbooks usually rely less on dense numeric computation and more on **semi-structured tables**, categorization fields, and mapping relationships across sheets. A professional parser for BA files should therefore be strong at detecting logical tables, multi-column text records, cross-references, and layout cues that separate sections of analysis rather than just reading plain rectangular data.

### 3.2 Data Analyst (DA)

**Use case.**  
A data analyst uses Excel to clean data, inspect distributions, summarize business performance, build dashboards, and communicate insights through aggregated views. This is closely aligned with the spreadsheet’s strengths in summarization and visual analysis: Microsoft explicitly positions PivotTables and PivotCharts as tools to summarize, analyze, explore, and present data, and to build interactive dashboards with slicers, timelines, and linked views. IBM’s data analyst training materials also continue to treat Excel spreadsheets as a practical tool in the analyst workflow.

**Typical Excel file features.**  
DA-oriented workbooks usually have a **raw-data sheet plus one or more summary or dashboard sheets**. Typical signals include long row-based datasets, typed columns, calculated fields, PivotTables, PivotCharts, KPI blocks, slicers, timelines, filters, conditional formatting, and chart-heavy summary pages. These workbooks are usually more quantitative than BA files and more presentation-oriented than accounting ledgers. A parser for DA files should preserve worksheet roles, detect large tabular regions, retain formula columns, and capture dashboard-linked objects and summary structures without flattening the workbook into CSV mush.

### 3.3 Project Manager (PM)

**Use case.**  
A project manager uses Excel to coordinate schedules, milestones, budgets, resource assignments, risks, issue logs, and progress reporting. PMI and BLS both describe project management work in terms of coordinating budget, schedule, staffing, and other project details, while PMI materials repeatedly refer to work breakdown structures, schedules, Gantt-style planning, and risk-oriented tracking artifacts.

**Typical Excel file features.**  
PM workbooks often contain **task tables**, owner columns, start and end dates, milestone flags, dependency references, percent-complete fields, cost columns, issue logs, and risk registers. Visually, they may include Gantt-like timeline layouts, milestone charts, or schedule summary sheets. They are often multi-sheet workbooks, with one sheet for the work plan, another for risks or issues, and another for status reporting. A parser for PM files should therefore handle date-rich structures, hierarchical task plans, progress metrics, and logs/registers that are operational rather than purely financial or analytical.

### 3.4 Human Resources (HR)

**Use case.**  
HR teams use Excel for employee records, attendance monitoring, workforce planning, performance-cycle support, recruitment tracking, training matrices, and HR information management. SHRM highlights attendance management, HRIS design, record-keeping, and performance management as core HR operational areas, while BLS describes HR specialists as working across recruiting, screening, interviewing, placement, and related HR activities.

**Typical Excel file features.**  
HR workbooks typically contain **entity-record tables**: one row per employee, applicant, department member, attendance entry, training record, or review cycle entry. Common patterns include date-heavy columns, status categories, department/team fields, note columns, compliance-related fields, and moderate use of conditional formatting to highlight absences, overdue reviews, or candidate stages. Compared with finance workbooks, HR files are less formula-dense; compared with BA files, they are more record-oriented and operational. A parser for HR spreadsheets should prioritize stable row-level extraction, date normalization, category handling, and preservation of comments or notes.

### 3.5 Accountant

**Use case.**  
Accountants use Excel to prepare and examine financial records, reconcile accounts, assemble statements, review balances, track payroll-related entries, and support reporting. The U.S. Bureau of Labor Statistics describes accountants and auditors as preparing and examining financial records, while AICPA/CIMA job postings emphasize reconciliations, general ledger work, sub-ledger checks, payroll-related entries, and financial reporting.

**Typical Excel file features.**  
Accounting workbooks are usually the most **regular and ledger-like** of the stakeholder groups. Common signals include transaction tables, account codes, debit/credit columns, posting dates, reference numbers, subtotal and total rows, roll-up formulas, reconciliation sections, and statement-style sheets. They often use strong border formatting and carefully positioned totals because the workbook is part calculation engine, part report. A parser for accountant files should be good at detecting repeated financial row schemas, subtotal logic, formula-based rollups, and relationships between detailed transaction sheets and summary statement sheets.

### 3.6 Computer Science (CS) / Technical Student

**Use case.**  
This category is less standardized than the others. CS students and technical users may use Excel for benchmark tracking, experiment logging, grade calculations, bug or issue summaries, lightweight dataset inspection, resource planning, or project status tracking. There is no single canonical “CS spreadsheet” artifact in the way there is for a ledger or attendance table. Research on spreadsheet benchmarks emphasizes that real-world spreadsheet use cases are highly diverse rather than neatly uniform, and Microsoft’s student-oriented spreadsheet pages also lean toward planning, assignment tracking, and lightweight organization rather than one fixed technical format.

**Typical Excel file features.**  
CS-oriented workbooks are therefore best described as **heterogeneous**. They may contain experiment tables, runtime or accuracy comparisons, grading matrices, issue trackers, task lists, or mixed technical logs. Typical patterns include metric columns, scenario/run identifiers, comparison tables, date/version fields, and occasional charts used to compare results across algorithms or iterations. A parser should not overfit to one structure here. Instead, it should be robust to semi-structured technical tables, sparse metadata, multiple small worksheets, and ad hoc layouts created by students or engineering teams in a hurry—which is a wonderfully chaotic human tradition.
