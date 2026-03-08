# Client Financial Analysis with Excel

<img align="right" alt="Client Financial Analysis with Excel" width="1000" height = "500" src="https://user-images.githubusercontent.com/106287208/187007496-33b3b2c1-1016-4b51-ba78-a588eab3c48b.png">

---


# Table of Contents

- [Problem Statement](https://github.com/globalsmile/Client-Finacial-Analysis#Problem-Statement)
- [Data Sourcing](https://github.com/globalsmile/Client-Finacial-Analysis#Data-Sourcing)
- [Data Preparation](https://github.com/globalsmile/Client-Finacial-Analysis#Data-Preparation)
- [Data Modeling](https://github.com/globalsmile/Client-Finacial-Analysis#Data-Modeling)
- [Data Visualization](https://github.com/globalsmile/Client-Finacial-Analysis#Data-Visualization)
- [Data Analysis](https://github.com/globalsmile/Client-Finacial-Analysis#Data-Analysis)
- [Insights](https://github.com/globalsmile/Client-Finacial-Analysis#Insights)
- [Shareable link](https://github.com/globalsmile/Client-Finacial-Analysis#Shareable-link)


---

# Problem Statement

Using the client's financial data:
- Help the client unlock the potential of analysis and reporting
- Produce everything the client need to know about her finances

---

# Data Sourcing

The Dataset used for this analysis was presented by [Finex Skills Hub](https://www.finexskillshub.com) and available at:

- [Client Finance Data](https://github.com/globalsmile/Client-Financial-Analysis/blob/main/Client%20Financial%20Data.xlsx)

---

# Data Preparation

Data transformation was done in Power Query and the dataset was loaded into Microsoft Excel Power Pivot for modeling.

The client's financial data consists of  2 worksheets containing 2 tables:

- `Transactions` which has `4 columns and 296 rows` of observation
- `Budget` which has `15 columns and 24 rows` of observation

The tabulation below shows the `Transactions` table with its column names and their description:
| Column Name | Description |
| ----------- | ----------- |
| Date | Represents the date of the transaction |
| Description | Describes the transaction narration |
| Category | Describes the category of the transaction |
| Amount | Represents the amount  of the transaction |

The tabulation below shows the `Budget` table with its column names and their description:
| Column Name | Description |
| ----------- | ----------- |
| Category | Describes the category of the budget |
| Class | Describes the class of the budget |
| Type | Describes the the type of the budget |
| Jan 2021 - Dec 2021 | Represents the budget amount for each month respectively |


Data Cleaning for the dataset was done in power query as follows:

- For the `Budget` table, the columns from `Jan 2021` to `Dec 2021` where unpivoted
- The resulting `Attribute` and `Value` columns where renamed to `Date` and `Amount` respectively 
- Validated the accuracy of the of `Date` column by changing the type to `date only`
- Validated the accuracy of the of `Amount` column by changing the type to `whole number`
- A dimension table named `categories` was created by referencing the `Budget` table
- Unneccessary columns were removed from the `categories` table
- Duplicate rows were removed from `categories` table

To ensure the accuracy of the dates in the `Date` column each of the tables, a date table was created for referencing using the M-formula:

`{Number.From(List.Min(Transactions[Date]))..Number.From(List.Max(Transactions[Date]))}`

Here is a breakdown of what the formula does:

For the dataset, we want the start date to reflect the earliest to latest date that we have in the data: January 01, 2021 - December 01, 2021.

`Month`,` Month Name`, `Year` columns were extracted from the date table

The date table was named `Calender`.

---

# Data Modeling

After the dataset was cleaned and transformed, it was ready to be modeled(using Power Pivot).

- The `Calender` table was marked as the official date table in the dataset.
- A `one-to-many (*:1) relationship` was created between the `Budget` and the `Calender` tables using the `date` column in each of the tables
- A `one-to-many (*:1) relationship` was created between the `Transactions` and the `Calender` tables using the `date` column in each of the tables 
- A `one-to-many (*:1) relationship` was created between the `Transactions` and the `Categories` tables using the `Category` column in each of the tables
- A `one-to-many (*:1) relationship` was created between the `budget` and the `Categories` tables using the `Category` column in each of the tables 
- The realtioships formed in the data model is a `Star Schema` and is shown below:

<img align="right" alt="Data Model" width="1000" height = "400" src="https://user-images.githubusercontent.com/106287208/183560342-f5e144bd-ffe1-476e-a264-172b0b23462f.png">

---

# Data Visualization

Data visualization for the dataset was done using Microsft Excel:

- The `Dashboard` worksheet: Shows the Actual amount, Budget amount, Balance, etc of the client.

Figure 1 shows visualizations from `Dashboard` worksheet

| Figure 1 |
| ----------- |
| ![image](https://user-images.githubusercontent.com/106287208/187007496-33b3b2c1-1016-4b51-ba78-a588eab3c48b.png) |


---

# Data Analysis

Measures used in visualization are:

- Actual = `SUM(Transactions[Amount])`
- Balance = `SUM(Budget[Amount])`
- Balance = `[Budget]-[Actual]`


As shown from [Data Visualization](https://github.com/globalsmile/Client-Finacial-Analysis#Data-Visualization), It can be deduced that for the year ending December 2021:

- The client budgeted a total amount of `$230,502`
- The client spent a total amount of `$193,228`
- The client has a balance of `$37,274`

---

# Insights

As shown by [Data Visualization](https://github.com/globalsmile/Client-Finacial-Analysis#Data-Visualization), It can be deduced that:

- The client spent the most in the month of `January`
- The client spent the least in the month of `November`
- The client has spent the highest amount on `Social`


Key Note: The client has a monthly budget amount of more than `$16k`,also the client has been able to stay afloat of this budget amount and as such stable enough to warrant a monetary investment

---

# Shareable Link

You can interact with the dashboard here: 

[View Dashboard](https://badmus67-my.sharepoint.com/:x:/g/personal/mohammed_badmus67_onmicrosoft_com/EeAqCZw-wahIi8P5zP4KKHEB7QWpODKX0WIrna0LLl70PA?e=OLavxD)
