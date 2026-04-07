# Requirement_Doc.docx


## Requirement_Doc.docx


### Manual Testing Project: Requirement Document


#### Project Title

Zero Bank – Online Banking Application


#### Website

http://zero.webappsecurity.com/


#### Tester

Tanay Puranik


#### Date

19/7/25


### 1. Project Overview

Zero Bank is a demo online banking application that simulates the basic functionalities of a banking system. The goal is to test the user experience, data validation, and functionality of the key features available to users.


### 2. Scope of Testing

The following modules will be tested manually:
- Login
- Account Summary
- Transfer Funds
- Feedback Form
- Logout


### 3. Functional Requirements


#### 🔐 Module 1: Login

- System must allow users to login with valid credentials.
- Invalid login attempts should show proper error messages.
- "Forgot your password" should redirect properly.


#### 📊 Module 2: Account Summary

- User must see current account balances.
- Different account types must display (Checking, Savings, etc.).


#### 🔁 Module 3: Transfer Funds

- Allow transfer from one account to another.
- Validate negative and empty values.
- Show success message upon valid transfer.


#### 📩 Module 4: Feedback Form

- Should allow users to submit feedback.
- Fields: Name, Email, Subject, Comment.
- Form validations must be in place.


#### 🚪 Module 5: Logout

- Clicking "Logout" should end the session.
- User must be redirected to login page after logout.


### 4. Non-Functional Requirements

- Website should be accessible on Chrome and Firefox.
- All pages should load within 3 seconds.
- Mobile compatibility testing (optional).


### 5. Assumptions

- The site is a demo and will not save data.
- Valid login credentials are public: username: username, password: password.


### 6. Tools Used

- Manual Testing
- Excel (for test cases and reports)
- JIRA (for tracking bugs, stories, and progress)
