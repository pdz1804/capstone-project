# HR Attrition Analytics Dashboard: Risk Segmentation & Cost Impact Analysis

## 1. Project Purpose and Business Relevance

This project moves beyond descriptive HR reporting to demonstrate how **data-driven risk segmentation** can support strategic workforce decisions.

**Primary objectives:**
1. **Attrition Risk Identification:** Identify high-risk employee segments by analysing satisfaction, workload, compensation, tenure, and demographic variables.
2. **Business Impact Translation:** Quantify employee attrition in financial terms to support prioritisation of retention interventions.

The output is an interactive Excel-based analytics dashboard that enables decision-makers to understand **where attrition risk is concentrated**, **which factors amplify that risk**, and **which segments should be addressed first for maximum impact**.

---

## 2. Core Metrics and DAX-Based KPIs

The analytical foundation of the dashboard is built using Power Pivot and DAX measures, ensuring metric consistency across all slicers and views.

| KPI | Definition | Business Interpretation |
|---|---|---|
| **Total Employees** | `COUNTROWS(HR_Data)` | Workforce baseline for all rate calculations |
| **Attrition Count** | Employees where Attrition = "Yes" | Absolute turnover volume |
| **Attrition Rate** | `DIVIDE(Attrition Count, Total Employees)` | Primary risk metric used as the organisational baseline (16.08%) |
| **Estimated Attrition Cost** | `SUMX(FILTER(HR_Data, Attrition="Yes"), MonthlyIncome * 0.5)` | Approximated replacement cost (50% of monthly salary assumption) |
| **Avg Cost per Attrition** | Attrition Cost / Attrition Count | Enables role- and department-level cost comparison |

> **Note:** Financial assumptions are intentionally simplified and explicitly stated to ensure transparency and analytical defensibility.

---

## 3. Analytical Framework and Key Insights

### 3.1 Interactive Control Dashboard

The main dashboard consolidates core KPIs and serves as the control layer for the entire analysis.  
All visuals are dynamically linked using slicers (Department, Job Role, Age Group, OverTime, Gender, etc.), enabling contextual drill-down without recalculating metrics.

![Main Dashboard](Images/HR_Attrition_Dashboard.png)

---

### 3.2 Workload & Overtime Risk Analysis

This section evaluates whether workload intensity is associated with higher attrition risk.

**Key insights:**
- Employees working overtime exhibit attrition rates nearly **3x higher** than those who do not.
- When overtime is combined with low satisfaction or weak work-life balance, attrition risk increases further, indicating **interaction effects rather than isolated drivers**.

![Compensation and Workload Analysis](Images/Copensation.png)

---

### 3.3 Job Satisfaction & Work-Life Balance

These factors show the strongest deviation from the company baseline.

**Observed patterns:**
- Employees with **low work-life balance** show attrition rates close to **31%**, compared to the organisational average of **16%**.
- High satisfaction and strong work-life balance consistently reduce attrition below baseline, identifying these as **high-impact retention levers**.

![Satisfaction Analysis](Images/Satisfaction.png)

---

### 3.4 Career Progression & Stagnation Risk

This analysis focuses on tenure and promotion timelines to identify stagnation-driven attrition.

**Key insights:**
- Employees with moderate tenure but long gaps since last promotion show elevated attrition risk.
- This suggests stagnation risk emerges **before long-term tenure**, supporting earlier intervention strategies.

![Career Progression Analysis](Images/Carrer_Progression.png)

---

### 3.5 Demographic & Departmental Segmentation

Attrition risk is unevenly distributed across departments and demographic groups.

**Purpose of this view:**
- Identify concentrated risk pockets rather than general trends
- Support targeted interventions instead of organisation-wide policies

![Demographic Analysis](Images/Demographic_Analysis.png)

---

## 4. Technical Implementation & Skills Demonstrated

### 4.1 Data Modelling & Power Pivot
- Centralised data model enabling consistent calculations across all visuals
- Efficient slicer connectivity across multiple PivotTables
- Clear separation between raw data, calculated measures, and presentation layers

### 4.2 DAX for Business-Oriented Metrics
- Use of `CALCULATE`, `FILTER`, `SUMX`, and `DIVIDE` to preserve metric integrity under filtering
- KPI design focused on decision support rather than vanity metrics
- Explicit handling of assumptions and denominator consistency

### 4.3 Dashboard Design & Usability
- Executive-friendly layout prioritising signal over clutter
- Real-time interactivity without manual recalculation
- Designed for non-technical users to independently explore attrition drivers

---

## 5. Practical Use Case

In a real organisational context, this dashboard would support:
- Identification of high-risk employee segments for targeted retention programmes
- Estimation of financial upside from reducing attrition in specific roles or departments
- Prioritisation of HR interventions based on **risk magnitude and cost impact**

---

## 6. Access Instructions

1. Download `HR_Attrition_Dashboard.xlsx`
2. Open using Microsoft Excel (2016 or newer recommended)
3. Use slicers to explore attrition risk across multiple dimensions






