# FunctionalRequirementSpecification


## 1. Purpose of the document:

This is not a project plan. It is a guide for system architecture and development, not for phasing, timelines or deliverables.
This document is divided into three sections:
• Project Overview
• Information Architecture
• Site Design


## 2. Project Overview:


### 2.1 Audience:

This document is intended as a complete guide for ESS-User in using OrangeHRM 3.0. This
document is specially designed for non-specialists; specialists may find the document a useful point of reference. By reading this guide, you will learn how to use OrangeHRM through the elements of the graphical user interface and what's behind some of the advanced features that are not always obvious at first sight. It will hopefully guide you around some common problems that frequently appear for users of OrangeHRM.


### 2.2 Hardware and Hosting:

OrangeHRM’s servers will be hosted at X company’s site.
OrangeHRM will be hosted on two servers: One to host the actual website and (language)code, and the other to host the (database name)database.


## 3. Information Architecture

Log in to the OrangeHRM System using your ESS-User account that has been created by the HR Admin as shown in Figure 1.0.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_1_4bdb3b7d.emf|4bdb3b7d2edd59ff9fb4ad9e684d81ad [END_IMAGE_PATH]


### 3.1 My info Module

My Info Module is a powerful tool providing employees of the company with the ability to view relevant information such as personal information and updating personal information with an internet enabled PC without having to involve the HR department.
The functionality of this module spans through the entire system, making information available anywhere, anytime. All information is subject to company’s defined security policy, where he/she can only view the information he/she is authorized to. An ESS-User can only edit certain fields in the ESS Module, maintaining the security and confidentiality of employee information


#### 3.1.1 My Info Module

When an ESS-User logs into the system for the first time, the first thing they will see is the “Personal Details” screen as shown in Figure 1.1. They are able to edit and enter certain fields.
Figure 1.1: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_2_260b626a.emf|260b626a064572768ec195c4a4af1a54 [END_IMAGE_PATH]The following are restricted fields where an ESS-User cannot make changes to the following details and need to be populated by the HR Admin and the respective ESS-Supervisor.
Personal Details
● Employee ID
● SSN No
● SIN No
● Driver License No
● Date of Birth


#### 3.1.2 Photograph

The ESS-User can add a photograph of himself/herself by clicking on the photograph at corner of the screen and the screen as shown in Figure 1.2 will appear. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_3_daa71aa9.emf|daa71aa9cd1ef319980a7c0f740f1ed3 [END_IMAGE_PATH]Click “Browse” and then select a photograph from the relevant path. Click “Upload” once you have selected the picture .The picture selected will be populated on the photograph section.
*Note: You may only upload a maximum size of 1 Megabyte in jpg, png, gif format.


#### 3.1.3 Contact Details

Contact information can be entered from here. Click on “Contact Details” under the Employee Details column and the screen as shown in Figure 1.3 will appear.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_4_d9c93e20.emf|d9c93e2074153c325f73fc10d1b403f9 [END_IMAGE_PATH]
Click “Edit” to enter the information.
You can edit the following:
 Country – Select the country from the drop down
 Street 1
 Street 2
 City/Town
 State/Province – If the country is United Sates you can select from the drop down or you need to enter it manually
 ZIP Code
 Home Telephone
 Mobile
 Work Telephone
 Work Email
 Other Email
Once you have completed this form click “Save”.


#### 3.1.4 Emergency Contact

Contact details which will be needed during an emergency can be entered here. Select “Emergency Contacts” on the “Personal” column and the screen as shown in Figure 1.4 will appear. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_5_5883f0b4.emf|5883f0b420b5ac614b52f996d4aeb69d [END_IMAGE_PATH]Enter the “Name” of the person you wish the company to contact in case of emergency, your “Relationship” with the contact person provided and a “Home Telephone” or “Mobile Number” the company can reach him/her.
Click “Save” once the fields are added, the emergency contact will be listed as shown in Figure 1.5.[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_6_ac3db3fe.emf|ac3db3fe094df680cad24cf578447a04 [END_IMAGE_PATH]You may add multiple entries of emergency contacts.
To delete an entry, click on the check box next to particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
You may also upload any attachment that would support the details you have entered on the form by clicking “Add” under the “Attachment” and selecting a file from a relevant path and upload the following file by clicking “Upload”.


#### 3.1.5 Dependants

If you have any dependents you can enter them here. To add a dependent, click on “Dependents” under the “Personal” column and the screen as shown in Figure 1.6 will appear. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_7_6fc07655.emf|6fc0765576bbe6d934d12176929c3509 [END_IMAGE_PATH]
Enter the “Name” of your dependent, the “Relationship” of the dependent to you and his/her “Date of Birth”.
Click “Save” once you have entered the following fields and your dependent will be listed as shown in Figure 1.7.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_8_600455ff.emf|600455ff8a3d9bb079e48de7aa456e45 [END_IMAGE_PATH]
You may add multiple entries of dependants.
To delete an entry, click on the check box next to particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
You may also upload any attachment that would support the details you have entered on the form by clicking “Add” under the “Attachment” and selecting a file from a relevant path and uploading the following file by clicking “Upload”.


#### 3.1.6 Immigration

Your immigration information can be entered here. To add your immigration information, select “Immigration” under the “Personal “column and the screen as shown in Figure 1.8 will appear. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_9_6ec80a87.emf|6ec80a87c7c2bbd0228b301734b4b266 [END_IMAGE_PATH]
Select the document type (Passport or Visa) you wish to add details of, the “Number” whether it is a passport number or a visa number, the “ Issued Date” , “Expiry Date”, the “Eligible Status” of your Passport/Visa and the “Eligible Review Date” as to when the eligibility status was reviewed. You may write a comment if necessary.
Click “Save” once the fields are added and the following immigration documents will be listed as shown in Figure 1.9. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_10_bbc6210b.emf|bbc6210b4d71663a9293fbb9ea6374d1 [END_IMAGE_PATH]
You may add multiple entries of immigration documents.
To delete an entry, click on the check box next to particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
You may also upload any attachment that would support the details you have entered on the form by clicking “Add” under the “Attachment” and selecting a file from a relevant path and uploading the following file by clicking “Upload”.


#### 3.1.7 Job

The ESS-User cannot make changes in the job details. You are only able to view your job details that have been pre-defined by the administrator as shown in Figure 2.0. You are restricted from editing the following fields:
● Job Title
● Jobs Specification
● Employment Status
● Job Category
● Joined Date
● Sub Unit
● Location
● Employment Contract Start Date
● Employment Contract End Date
● Attachments
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_11_8e45161c.emf|8e45161c93ac42e7bdaa93c69870bcbb [END_IMAGE_PATH]


#### 3.1.8 Salary

The salary information field is completely hidden from the ESS-User as shown in Figure 2.1. Only the HR Admin has access to this information and has to be manually communicated to the ESS-User. You are restricted from editing the following fields:
Salary
● Salary Component
● Pay Frequency
● Currency
● Amount
● Comments
● Direct Deposit Details
● Attachments[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_12_ab791cea.emf|ab791cea62dbe53ae9e0f251f8ea9604 [END_IMAGE_PATH]


#### 3.1.9 Report To

As an ESS-User, you are only able to view the list of supervisors that you report to and if you are an ESS-Supervisor as well, you will see the list of your subordinates as shown in Figure 2.2.
You are restricted from editing the following fields:
● Assigned Supervisors
● Assigned Subordinates
● Attachments
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_13_597476c2.emf|597476c262201d2d31b466e269e0639d [END_IMAGE_PATH]


#### 3.1.10 Qualifications

● Work Experience
Your previous work experiences can be entered here. To enter previous work experiences, click “Add” under “Work Experience” and the screen as shown in Figure 2.3 will appear.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_14_54c51a52.emf|54c51a52e0c7a3d3286b3a1a996619e8 [END_IMAGE_PATH]
Click “Save” once all the fields are entered and the particular work experience will be listed as shown in Figure 2.4.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_15_78648baf.emf|78648baf98ec165361983dcb9716f0bb [END_IMAGE_PATH]
You may enter multiple entries of work experience.
To delete an entry, click on the check box next to a particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
● Education
You are able to enter details of your education here. To enter education details, click “Add” under “Education” and the screen as shown in Figure 2.5 will appear.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_17_19417673.emf|19417673eef92ac43bbf20298a817110 [END_IMAGE_PATH]
Click “Save” once all the fields are entered and the particular education details will be listed as shown in Figure 2.6. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_16_259587c1.emf|259587c1803b23912857780ad146cc7f [END_IMAGE_PATH]
You may enter multiple entries of education.
To delete an entry, click on the check box next to particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
● Skills
If you have any special talents or skills they can be entered here. To enter skills, click “Add” under “Skills” and the screen as shown in Figure 2.7 will appear.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_18_eff8d0d2.emf|eff8d0d273de30f7d672ef2563e00434 [END_IMAGE_PATH]
Click “Save” once all the fields are entered and the particular skill will be listed as shown in Figure 2.8.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_19_21291b39.emf|21291b39024b82eae1c502cc0996cc18 [END_IMAGE_PATH]
You may enter multiple entries of skills.
To delete an entry, click on the check box next to particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
● Languages
You can enter the various languages that you are competent in, with the level of competency. To enter your language of competency, click “Add” under “Language” and the screen as shown in Figure 2.9 will appear.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_21_0487520b.emf|0487520b3f02bf70cce7bb083bbfdee1 [END_IMAGE_PATH]
Click “Save” once all the fields are entered and the particular language of competency will be listed as shown in Figure 3.0. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_20_0e2fae4f.emf|0e2fae4f7addb172f662117c700e3f3a [END_IMAGE_PATH]
You may enter multiple entries of languages.
To delete an entry, click on the check box next to particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
● License
Here you can enter the licenses that you may have. To enter licenses, click “Add” under “License” and the screen as shown in Figure 3.1 will appear.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_22_6bf5d567.emf|6bf5d5678adeb99880e2c3b5775575b9 [END_IMAGE_PATH]
Click “Save” once all the fields are entered and the particular license will be listed as shown in Figure 3.2
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_23_dea395c2.emf|dea395c20dcb5b762e16c09bb02ed11c [END_IMAGE_PATH]
You may enter multiple entries of licenses.
To delete an entry, click on the check box next to particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
● Attachments
Any supporting documents regarding your qualification that you think is needed by the management can be attached here. Please note that each document cannot exceed 1 megabyte, but you can attach more than one document. To add an attachment, click “Add” under attachment and the screen as shown in Figure 3.3 will appear.
Click “Browse” and select the file from the relevant path and click “Upload” to upload it.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_24_f613b0b6.emf|f613b0b663330f2a1e0516fbf36fb891 [END_IMAGE_PATH]
Once you have uploaded the file, the file will be listed as shown in Figure 3.4
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_25_5bea8149.emf|5bea8149df5746a3a70845bfdc116a7e [END_IMAGE_PATH]
You may upload multiple attachments.
To delete an entry click on the check box next to the particular entry and click “Delete”. Multiple selections can be deleted simultaneously.


#### 3.1.11 Membership

If you are a members of any committee, institute etc. those details can be entered here. To enter membership details, go to My Info>>Personal>>Membership and click “Add” and the screen as shown in Figure 3.5 will appear.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_27_e0b71969.emf|e0b71969d751e3da628b5e497f3f2716 [END_IMAGE_PATH]
Click “Save” once all the fields are entered and the particular membership detail will be listed as shown in Figure 3.6. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_xubs0yn2/img_26_1a53a8e6.emf|1a53a8e6c4a06da02ea760bf8f92dfdd [END_IMAGE_PATH]
You may enter multiple entries of memberships.
To delete an entry, click on the check box next to particular entry. It is also possible to delete multiple entries at the same time by clicking the check box entries you wish to delete and simply clicking “Delete”.
You may also upload any attachment that would support the details you have entered on the form by clicking “Add” under the “Attachment” and selecting a file from a relevant path and upload the following file by clicking “Upload”.


## 4. Sign-Off Document

_____________________________________________________________________________
The following parties have read and agree with this Requirements Definition document for the OrangeHRM application account module functionality.
After approval of this Requirements Definition phase, any significant changes in the scope of this project will require validation of existing project costs and schedules.
______________________________________  _________________________________
Name       Date
Business Lead
______________________________________ ________________________________
Name       Date
Project Manager
