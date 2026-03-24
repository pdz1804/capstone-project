# Personal Budget

## A simple Excel spreadsheet to help manage personal finances.

I created this spreadsheet to improve my financial organization, build a financial plan, and track where my money was going. My goal was to keep it simple and user-friendly, with each financial transaction entered on a single line, ***automatically updating*** all related sheets.

<br>

![Image](https://github.com/user-attachments/assets/3714527b-8185-4038-b30c-48293db23948)  
*Balance & Tracking Sheet*

---

## Features

This Personal Budget is composed of six different sheets, each addressing a key financial area:

1. **Data Validation** – Sets category names and account information.
2. **Balance & Tracking** – Records all financial operations.
3. **Net Salary** – Tracks income, deductions, and investments by month.
4. **Expenses** – Logs categorized expenses by month.
5. **Dashboard** – Displays relevant annual financial insights.
6. **Analysis** – Provides insights based on transaction descriptions.

---

## Download

To download and edit the spreadsheet:

1. Click on one of its versions (e.g., `'Personal Budget - English.xlsx'`).
2. Select **'View raw'**.
3. Once downloaded, open the file and click **'Enable Editing'**.

---

## Usage

This spreadsheet is designed to help you easily track your income and expenses.

### 1 - Setting Up (Data Validation Sheet)

- Open the file and navigate to the **Data Validation** sheet.
- Set the initial balance for each account and customize category names to match your spending habits.  
⚠️ *Important: Once categories and balances are set, avoid changing them to prevent calculation errors.*

---

### 2 - Tracking Financial Operations (Balance & Tracking Sheet)

Go to the **Balance & Tracking** sheet. This sheet includes tables and a graph that automatically update based on your entries in the **Tracking** table.

---

### 2.1 - Monthly Summary Table

- In **cell B2**, the month updates automatically based on the date entered in **cell C7**.
- The summary below displays:
  - **Balance** – Income minus expenses, plus any carry-over from the previous month.
  - **Monthly expenses**
  - **Net salary** – Can be toggled via **cell B4**.

---

### 2.2 - Expenses & Net Salary Graph

- A visual overview of your expenses and net salary for the selected month.
- Toggle between views using **cell B4**.

---

### 2.3 - Account Table

- View a summary of your accounts, including Bank, Savings, Debt, and Credit Card.
- Use **cell C7** to select a date and view past or future account balances. If left blank, it defaults to today (`=TODAY()` in Excel).
- When logging a credit card purchase in the **Tracking** table, the corresponding credit card row changes color to indicate a payment is due.
  - To record a payment, select **'Payment'** as the operation and choose **'Credit Card'** under **'Account'**. The same applies to other liability accounts.
- The **Account** table is designed with four rows for positive balances (e.g., Bank, Savings) and two for liabilities (e.g., Credit Card).
  - In the **Data Validation** sheet, you can customize each label (e.g., JPMorgan, Bank of America, Wells Fargo, Amex, Visa, etc.).

---

### 2.4 - Tracking Table

- This is the core of the spreadsheet. Enter each financial operation by selecting a category and entering the amount.
- Transactions are sorted by **date**, not by the order in which they were entered.
- You can use the filters in the table header to display only the information you want to see.  
- All other tables and graphs update automatically based on this table.
- 💡 *Tip: Press the `Tab` key to move between fields and quickly create a new row at the bottom.*

---

## ⚠️ Important: Date Logic

The date of an operation affects **Accounts** and **Monthly Balance** differently:

- Operations **dated in the future** affect **only the Monthly Balance** for the current month.
- Operations **dated today or earlier** affect **both Accounts and Monthly Balance**.

As a result:

- If the values of **Accounts** and **Monthly Balance** match, **cell C3 turns green**.
- If they differ, **cell C3 turns orange** to signal a mismatch.

---

## 💡 Tips

You can create a financial plan by entering future-dated operations.  
For example: salaries, bills, travel, and deductions you expect in the coming months.  
This helps you make better decisions by forecasting your financial situation.

📌 *For a better experience, adjust the zoom and press `Ctrl + F1` to hide the ribbon and focus on the spreadsheet.*

---