# Testplan


## Testplan


### Table of contents

Overview          2  
Scope           2  
Inclusions          2  
Test Environment        2  
Exclusions          2  
Test Strategy         3  
Defect Reporting Procedure       4  
Roles/Responsibilities        4  
Test Schedule          5  
Test Deliverables         5  
Entry and Exit criteria        6  
Tools           6  
Risks and Mitigations        7  
Approvals             8


### Overview

In this documents includes how to test the functionalities of the web application https://demo.opencart.com/  
This document serves as high level test planning document with details on the scope of the project, test strategy, test schedule and resource requirements, test deliverables and schedule.


### Scope

The scope of the project includes testing the following features of ‘https://demo.opencart.com/’ web application.


### Inclusions

• Register  
• Login & Logout  
• Forgot Password  
• Search  
• Product Compare  
• Product Display Page  
• Add to Cart  
• Wish List  
• Shopping Cart  
• Currencies  
• Home Page  
• Checkout Page  
• My Account Page  
• Order History Page  
• Downloads Page  
• Contact Us Page  
• Menu Options  
• Footer Options  
• Category Pages


### Test Environment

• The operating systems that will be used for testing, such as Windows 10  
• The browsers that will be used for testing such as Google Chrome, Mozilla Firefox, or Microsoft Edge.  
• The network connectivity and bandwidth that will be available for testing, such as Wi-Fi, cellular, or wired connections.


### Exclusions

All the features except that are mentioned under Inclusions


### Test Strategy

Step 1 – Creation of Test Scenarios and Test Cases for the different features in scope.  
• We will apply several Test Designing techniques while creating Test Cases  
  o Equivalence Class Partition  
  o Boundary Value Analysis  
  o Decision Table Testing  
  o State Transition Testing  
• We prioritise the Test Cases  

Step 2 – Our Testing process, when we get an Application for Testing:  
• Firstly, we will perform Smoke Testing to check whether the different and important functionalities of the application are working.  
• We reject the build, if the Smoke Testing fails and will wait for the stable build before performing in depth testing of the application functionalities.  
• Once we receive a stable build, which passes Smoke Testing, we perform in depth testing using the Test Cases created.  
• We then report the bugs in bug tracking tool and send to developer, management the defect found on that day in a status end of the day email.  
• As part of the Testing, we will perform the below types of Testing:  
  o Smoke Testing and Sanity Testing  
  o Regression Testing and Retesting  
  o Usability Testing, Functionality & UI Testing  
• We repeat Test Cycles until we get the quality product.


### Defect Reporting Procedure

• Any deviation from expected behaviour by the application will be noted.  
• The steps for reporting a defect, such as using a designated template, providing detailed reproduction steps, and attaching screenshots or logs.  
• The tools and systems that will be used for tracking and managing defects, such as a defect tracking software or a project management tool.  
• Every day, at the end of the test execution, defects encountered will be sent along with the observations.


### Test Schedule

Following is the test schedule planned for the project  

[START_TABLE_CONTENT] | Task | Time Duration |  
| --- | --- |  
| Creating Test Plan | 30.11.2023 |  
| Test Case Creation | 12.12.2023 |  
| Test Case Execution |  |  
[END_TABLE_CONTENT]


### Test Deliverables

The following are to be delivered to the client:  

[START_TABLE_CONTENT] | Deliverables | Description | Target completion date |  
| --- | --- | --- |  
| Test Plan | Details on the scope of the Project, test strategy, test schedule, resource requirements, test deliverables and schedule | 30.11.2023 |  
| Functional Test Cases | Test Cases created for the scope defined | 24.12.2023 |  
| Defect Reports | Detailed description of the defects identified along with screenshots and steps to reproduce on a daily basis. | NA |  
[END_TABLE_CONTENT]


### Entry and Exit Criteria

The below are the entry and exit criteria for every phase of Software Testing Life Cycle:


#### Requirement Analysis

Entry criteria:-  
The testing team receives the requirement documents or details about the project  
Exit criteria:-  
• List of Requirements should explored and understood by the testing team  
• Doubts are need to be clarified


#### Test Planning

Entry criteria:-  
• Testable requirements are derived from given requirement document or project details  
• Doubts are need to be clarified  
Exit criteria:-  
• Test plan document need to created  
• Test plan document is signed off by the client


#### Test Designing

Entry criteria:-  
• Test plan document is signed off by the client  
Exit criteria:-  
• Test scenarios and test cases need to be created  
• Test scenarios and test cases is signed off by the client


#### Test Execution

Entry criteria:-  
• Test scenarios and test cases is signed off by the client  
• Application is ready for Testing  
Exit criteria:-  
• Test Case Reports, Defect Reports are ready


#### Test cycle closure

Entry criteria:-  
• Test Case Reports, Defect Reports are ready  
Exit criteria:-  
• Test Summary Report


### Tools

The following are the list of Tools we will be using in this Project:  
• Bug Tracking Tool  
• Snipping Screenshot Tool  
• Word and Excel documents


### Risks and Mitigations

The following are the list of risks possible and the ways to mitigate them:  
Risk: Non-Availability of a Resource  
Mitigation: Backup Resource Planning  
Risk: Build URL is not working  
Mitigation: Resources will work on other tasks  
Risk: Less time for Testing  
Mitigation: Ramp up the resources based on the Client needs dynamically


### Approvals

Team will send different types of documents for Client Approval like below:  
• Test Plan  
• Test Scenarios  
• Test Cases  
• Reports  
Testing will only continue to the next steps once these approvals are done
