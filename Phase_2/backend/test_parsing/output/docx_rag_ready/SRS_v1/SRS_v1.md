# SRS_v1


## 1. Introduction

The Guru99 Bank project aims to provide net banking facility to its customers.
This release will have limited features. Over a period of time , new and new functionalities will be added to the site.


### 1.1 Purpose

The Purpose of this document is to outline the requirements for the Guru99 Banking website to be developed for Guru99 Tech. Pvt. Ltd. This document will be used by all stakeholders including developers and testers.


### 1.2 Scope

The scope of this project is limited to the testing of the features described in the succeeding sections of this document.
Non-functional testing like stress,performance is beyond scope of this project.
Automation testing is beyond scope.
Functional testing & external interfaces are in scope and need to be tested
The banking site will be only compatible with Chrome version 27 and above


### 1.3 Definitions, Acronyms, and Abbreviations

[START_TABLE_CONTENT] | Abbreviation | Word |
| --- | --- |
| M | Manager |
| C | Customer | [END_TABLE_CONTENT]


### 1.4 References

Nil


## 2. Specific Requirements

The Guru99 Bank will have 2 roles
1. Manager
2. Customer
Following features/modules will be available to these 2 different roles

[START_TABLE_CONTENT] | Manager | Customer |
| --- | --- |
| New Customer | Balance enquiry |
| Edit Customer | Fund Transfer |
| Delete Customer | Mini Statement |
| New Account | Customized Statement |
| Edit Account | Change Password |
| Delete Account | Login & Logout |
| Deposit |  |
| Withdrawal |  |
| Fund Transfer |  |
| Change Password |  |
| Balance Enquiry |  |
| Mini Statement |  |
| Customized Statement |  |
| Login & Logout |  | [END_TABLE_CONTENT]

Description of the modules

[START_TABLE_CONTENT] | Module Name | Applicable. Roles | Description |
| --- | --- | --- |
| Balance Enquiry | Manager. Customer | Customer: A customer can have multiple bank accounts. He can view balance of his accounts only. Manager: A manager can view balance of all the customers who come under his supervision |
| Fund Transfer | Manager. Customer | Customer: A customer can have transfer funds from his “own” account to any destination account. Manager: A manager can transfer funds from any source bank account to destination account |
| Mini Statement | Manager. Customer | A Mini statement will show last 5 transactions of an account. Customer: A customer can see mini-statement of only his “own” accounts. Manager: A manager can see mini-statement of any account |
| Customized Statement | Manager. Customer | A customized statement allows you to filter and display transactions in an account based on date, transaction value. Customer: A customer can see Customized- statement of only his “own” accounts. Manager: A manager can see Customized -statement of any account |
| Change Password | Manager. Customer | Customer: A customer can change password of only his account. Manager: A manager can change password of only his account. He cannot change passwords of his customers |
| New Customer | Manager | Manager: A manager can add a new customer. |
|  | Manager | Manager: A manager can edit details like address, email , telephone of a customer. |
| New Account | Manager | Currently system provides 2 types of accounts. ● Saving. ● Current. A customer can have multiple saving accounts (one in his name , other in a joint name etc). He can have multiple current accounts for different companies he owns. Or he can have a multiple current and saving accounts. Manager: A manager can add a new account for an existing customer. |
| Edit Account | Manager | Manager: A manager can add a edit account details for an existing account |
| Delete Account | Manager | Manager: A manager can add a delete an account for a customer. |
| Delete Customer | Manager | A customer can be deleted only if he/she has no active current or saving accounts. Manager: A manager can delete a customer. |
| Deposit | Manager | Manager: A manager can deposit money into any account. Usually done when cash is deposited at a bank branch. |
| Withdrawal | Manager | Manager: A manager can withdraw money from any account. Usually done when cash is withdrawn at a bank branch. | [END_TABLE_CONTENT]


### 2.1 External Interface Requirements


#### 2.1.1 User Interfaces

None


#### 2.1.2 Hardware Interfaces

None


#### 2.1.3 Software Interfaces

None


#### 2.1.4 Communications Interfaces

None


### 3.1 Front End Details

This section describes the Front end of Guru99 Bank.
It also lists a few use cases to describe the functioning of the system
Following is a list of module wise fields
Fund Transfer
● Payers account no
● Payees account no
● Amount
● Submit
● Reset
Change Password
● Old Password
● New Password
● Confirm Password
● Submit
● Reset
Balance enquiry
● Account No
● Submit
● Reset
Mini Statement
● Account No
● Submit
● Reset
Customized Statement
● Account No
● From Date
● To Date
● Amount Lower Limit
● Number Of Transaction
● Submit
● Reset
New Customer
● Customer Name
● Gender
● Date of Birth
● Address
● City
● State
● PIN
● Telephone Number
● Email Id
● Submit
● Reset
New Account
● Customer Id
● Account Type
● Initial deposit
● Submit
● Reset
Deposit
● Account Number
● Amount Deposit
● Description
● Submit
● Reset
Withdraw
● Account Number
● Amount
● Description
● Submit
● Reset
Delete Customer
● Customer Id
● Submit
● Reset
Edit Account
● Account Number
● Submit
● Reset
Form after submitting Edit Account
● Customer Id
● Account Type (Drop Down - Saving or Current)
● Balance
● Submit
● Reset
Delete Account
● Account Number
● Submit
● Reset
Edit Customer
● Customer Id
● Submit
● Reset
Form after submitting Edit Customer
● Customer Name
● Gender
● Date of Birth
● Address
● City
● State
● PIN
● Telephone Number
● Email Id
● Submit
● Reset


### 3.2 Technical Requirements

New Account
T1    Customer Id - Customer ID is required
T2    Customer Id - Special character are not allowed
T3    Customer Id - Characters are not allowed
T3.1    Customer Id - First character cannot have space
New Customer
T4    Customer Name – Numbers are not allowed
T5    Customer Name – Special characters are not allowed
T6    Customer Name -  Customer name must not be blank
T7    Customer Name - First character cannot have space
T8    Address - Address Field must not be blank
T9    Address - First character can not have space
T10  Address - Special characters are not allowed
T11  City - Special character are not allowed
T12  City - City Field must not be blank
T13  City – Numbers are not allowed
T14  City - First character can not have space
T15  State – Numbers are not allowed
T16  State - State must not be blank
T17  State – Special characters are not allowed
T17.1  State – First character cannot have space
T18  Pin - Characters are not allowed
T19  Pin - PIN Code must not be blank
T20  Pin – Special characters are not allowed
T21  Pin – PIN Code must have 6 Digits
T22  Pin - First character can not have space
T23  Telephone Number – Mobile no must not be blank
T24  Telephone Number  – Special character are not allowed
T25  Telephone Number  – Character are not allowed
T26  Telephone Number - First character can not have space
T27  Email : Email ID must not be blank
T28  Email : Email ID is not valid
T29  Email : First character can not have space
Balance Enquiry
T30  Account No must not be blank
T31  Special character are not allowed
T32  Characters are not allowed
Customized Statement Form
T33  Account No - Account Number must not be blank
T34  Account No - Characters are not allowed
T35  Account No - Special characters are not allowed
T36  Amount Lower Limit – Special character are not allowed
T37  Amount Lower Limit – Amount Lower Limit is required
T38  Amount Lower Limit – Characters are not allowed
T39  Number of Transaction – Special character are not allowed
T40  Number of Transaction  - Number of Transaction must not be blank
T41  Number of Transaction – Character are not allowed
Delete Account Form
T42  Account No must not be blank
T43  Special character are not allowed
T44  Characters are not allowed
Delete Customer
T45  Customer Id - Customer ID is required
T46  Customer Id - Special character are not allowed
T47  Customer Id - Characters are not allowed
T47.1  Customer Id - First character cannot have space
Deposit
T48  Account No must not be blank
T49  Special character are not allowed
T50  Characters are not allowed
T51   Amount field must not be blank
T52   Special characters are not allowed
T53   Characters are not allowed
T54   Description must not be blank
Edit Account
T55   Account No must not be blank
T56   Special character are not allowed
T57   Characters are not allowed
Edit Customer form
T58   Customer Id - Customer ID is required
T59   Customer Id - Special character are not allowed
T60   Customer Id - Characters are not allowed
T60.1   Customer Id - First character can not have space
Edit Customer
T61   Address - Address Field must not be blank
T62   Address - First character can not have space
T63   Address - Special characters are not allowed
T64   City - Special character are not allowed
T65   City - City Field must not be blank
T66   City – Numbers are not allowed
T67   City - First character can not have space
T68   State – Numbers are not allowed
T69   State - State must not be blank
T70   State – Special characters are not allowed
T70.1   State – First character cannot have space
T71   Pin - Characters are not allowed
T71   Pin - PIN Code must not be blank
T72   Pin – Special characters are not allowed
T73   Pin – PIN Code must have 6 Digits
T74   Pin - First character cannot have space
T75   Telephone Number – Mobile no must not be blank
T76   Telephone Number  – Special character are not allowed
T77   Telephone Number  – Character are not allowed
T78   Telephone Number - First character cannot have space
T79   Email : Email ID must not be blank
T80   Email : Email ID is not valid
T81   Email : First character cannot have space
Fund Transfer
T82   Payers Account Number must not be blank
T83   Special characters are not allowed
T84   Characters are not allowed
T85   Payees Account Number must not be blank
T86   Special characters are not allowed
T87   Characters are not allowed
T88   Amount Field must not be blank
T89   Characters are not allowed
T90   Special characters are not allowed
T91   Description cannot be blank
Login
T92   User-ID must not be blank
T93   Password must not be blank
Mini Statement Page
T94   Account No must not be blank
T95   Special character are not allowed
T96   Characters are not allowed
Change Password
T97   Old Password must not be blank
T98   New Password must not be blank
T99   Enter at-least one numeric value
T100 Enter at-least one special character
T101 Choose a difficult Password
T102 Confirm Password must not be blank
T103 Passwords do not Match
Withdraw
T104 Account No must not be blank
T105 Special character are not allowed
T106 Characters are not allowed
T107 Amount Field must not be blank
T108 Characters are not allowed
T109 Special characters are not allowed
T110 Description cannot be blank


### 3.3 Functional validations

Balance Enquiry
Manager
F1 Manager can view balance of accounts associate with him
F2 Account number entered should exist in database
Customer
F3 Customer can view balance of only his accounts
F4 Account number entered should exist in database
Fund Transfer
Manager
F5 If these source and destination account numbers are invalid, system displays an error
F6 If these source and destination account numbers are same, system displays an error
F7 If the source account does not have the necessary balance, system displays an error
F8 If the source account does not associated with manager, System displays an error
Customer
F9 If the destination account number is not valid, system displays an error
F10 If these source and destination account numbers are same, system displays an error
F11 If the source account does not have the necessary balance, system displays an error
F12 If the source account is not associate with customer itself, System displays an error.
Withdrawal
Manager
F13 If source account number is invalid, system displays an error
F14 If source account does not have the necessary balance, system displays an error
F15 If source account does not associate with manager, System displays an error.
Customer
F16 If source account number is invalid, system displays an error
F17 If source account does not have the necessary balance, system displays an error
F18 If source account does not associate with customer, System displays an error.
Deposit
Manager
F19 If destination account number is invalid, system displays an error
F20 If destination account number does not associate with manager, System displays an error.
Customer
F21 If destination account number is invalid, system displays an error
F22 If destination account number does not associate with customer, System displays an error.
Delete Customer
Manager
F23 If Customer Id is invalid, system displays an error.
F24 If account associate with Customer Id, System displays an error.
F25 If Customer Id does not associate with manager, System displays an error.
Delete Account
Manager
F26 If Account Number is invalid, system displays an error
F27 If account does not associate with manager logged in, System displays an error.
Edit Account
Manager
F28 If Account Number is invalid, system displays an error.
F29 If Account number does not associate with manager, System displays an error.
New Account
Manager
F30 If Customer ID is invalid, system displays an error.
F31 If initial deposit is less than 500, System displays an error.
F32 If Customer Id does not associate with manager, System displays an error.
New Customer
Manager
F33 If same Email Id exist in the system, system shows an error.
Edit Customer
Manager
F34 If same Email Id exist in the system, system shows an error.
F35 If Customer Id is invalid, System displays an error.
F36 If Customer Id does not associate with Manager, System displays an error.
Change Password
Manager
F37 If Old Password is invalid, System shows an error.
Customer
F38 If Old Password is invalid, System displays an error
Customized Statement
Manager
F39 If account no is invalid, System displays an error
F40 If From Date is greater than To Date, System dispalys an error.
Customer
F41 If account no is invalid, System displays an error
F42 If From Date is greater than To Date, System dispalys an error.
Mini Statement
Manager
F43 If account no is invalid, System displays an error
F44 If transaction not exist in system, System displays an error.
F45 If account not associate with manager itself, System displays an error.
Customer
F46 If account no is invalid, System displays an error.
F47 If account associate with customer itself, System displays an error.
Balance Enquiry
Manager
F48 If account no is invalid, System displays an error
Customer
F49 If account no is invalid, System displays an error


### 3.4 Classes / Objects

3.5.1.1 Attributes
3.5.1.2 Functions


### 3.5 Non-Functional Requirements

Nil


### 3.6 Inverse Requirements

Nil.


### 3.7 Design Constraints

Many of the Guru99 Bank users may not have adequate computer knowledge to use the site. Hence, System must be intuitive and easy to understand.


### 3.8 Logical Database Requirements

Nil


### 3.9 Other Requirements

Nil


## 4. Analysis Models

Nil


## 5. Change Management Process

Changes to the SRS either from the development, testing team or the client side will be communicated to the project sponsor Mr Krishna Rungta.
Any change made to the SRS will require a sign off from the Development lead , QA lead and the client.
Once approved changed will be made to the SRS and the new SRS will be circulated to all stakeholders
A. Appendices
Nil
