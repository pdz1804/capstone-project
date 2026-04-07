# Data Warehouse

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_000_00.png|cd99595d9274 [END_IMAGE_PATH]
HO CHI MINH UNIVERSITY OF TECHNOLOGY, VNU-HCM
Faculty of Computer Science and Engineering
A S S I G N M E N T  P R E S E N T A T I O N


## Clustering

Group: 06
Course: Data warehouse and Decision Support System
Lecturer: Phan Trọng Nhân, PhD
1
[START_TABLE_CONTENT]
| Table of Content<br>01 Problem Statement<br>02 Data Warehouse Design<br>03 ELT Pipeline<br>04 Decision Support System Design<br>05 Conclusion<br>2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
[END_TABLE_CONTENT]
[START_TABLE_CONTENT]
|  | 04 |
| --- | --- |
|  |  |
[END_TABLE_CONTENT]


### 01 Problem Statement


#### Facts: Regions (cities, provinces) affects significantly in

consumer behavior,
income,
and infrastructure.


#### Our method: Market Region Clustering groups these areas based on

sales patterns and similarities rather than just geography.


#### Our targets: Enable business strategies

3


### 01 Problem Statement


#### Need-human processes: Organizations often rely on intuition rather

than reliable data to categorize regions.


#### Inconsistency: Issues lead to missed opportunities in emerging

markets and inability to identify underperforming areas.


#### Complexity: Without automated pipelines, extracting insights from

large datasets is inefficient.


#### The Need: A shift from manual segmentation to an automated, data-

driven clustering system.
4


### 01 Problem Statement


#### 1.Establish a Data Warehouse

Centralize and structure big data
Create a pipeline for data cleaning, integrating,  and organization.


#### 2.Develop a Decision Support System (DSS)

Apply clustering algorithms to identify market patterns.
Provide helpful insights for
strategic planning,
resource allocation,
operational improvements.
5


### 02 Data Warehouse Design

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_005_00.png|d4c3835b3da1 [END_IMAGE_PATH]
Figure 3.1: Data
Warehouse Shema
Diagram
6


### 03 ELT (Extract, Load, Transform)

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_006_00.png|49ce652c4873 [END_IMAGE_PATH]
7


### 03 ELT (Extract, Load, Transform)

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_007_00.png|50d25b99dc9d [END_IMAGE_PATH]
8


### 03 ELT (Extract, Load, Transform)


#### Setup Source/ Setup Destination for Airbyte Pipeline

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_008_00.png|c987ea929e55 [END_IMAGE_PATH]
9


### 03 ELT (Extract, Load, Transform)


#### Setup Source/ Setup Destination for Airbyte Pipeline

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_009_01.png|68dab05de1c2 [END_IMAGE_PATH]
[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_009_00.png|6d7bbd22fd6c [END_IMAGE_PATH]
10


### ELT (Extract, Load, Transform)

03


#### Incremental | Append (Newly Created Record)

[START_TABLE_CONTENT]
| name | deceased | updated at<br>_ |
| --- | --- | --- |
| Louis XVI | FALSE | 1754 |
| Marie<br>Antoinette | FALSE | 1755 |
[END_TABLE_CONTENT]
[START_TABLE_CONTENT]
| name | deceased | updated at<br>_ |
| --- | --- | --- |
| Louis XVII | FALSE | 1785 |
[END_TABLE_CONTENT]
Destination
Source
11


### ELT (Extract, Load, Transform)

03


#### Incremental | Append (Newly Created Record)

[START_TABLE_CONTENT]
| name | deceased | updated at<br>_ |
| --- | --- | --- |
| Marie Antoinette | FALSE | 1755 |
| Louis XVI | FALSE | 1754 |
| Louis XVII | FALSE | 1785 |
[END_TABLE_CONTENT]
12


### ELT (Extract, Load, Transform)

03


#### Incremental | Append (Updating a record)

[START_TABLE_CONTENT]
| name | deceased | updated at<br>_ |
| --- | --- | --- |
| Louis XVI | TRUE | 1793 |
| Marie<br>Antoinette | TRUE | 1793 |
[END_TABLE_CONTENT]
[START_TABLE_CONTENT]
| name | deceased | updated at<br>_ |
| --- | --- | --- |
| Louis XVI | TRUE | 1793 |
| Marie<br>Antoinette | TRUE | 1793 |
| Louis XVII | FALSE | 1785 |
[END_TABLE_CONTENT]
13


### ELT (Extract, Load, Transform)

03


#### Incremental | Append mechanism

[START_TABLE_CONTENT]
|  | Definition | Example / Purpose |
| --- | --- | --- |
| Cursor | Value used to determine if a record<br>should be included in an incremental<br>sync. | A timestamp indicating last update. |
| Cursor Field | The field/column where the cursor<br>value is stored. | updated at column in a table.<br>_ |
| Primary Key | One or multiple columns that<br>uniquely identify an entity. Used to<br>determine which record to update. | id column; composite keys like<br>(user id, order id).<br>_ _ |
[END_TABLE_CONTENT]
14


### ELT (Extract, Load, Transform)

03


#### Full Refresh | Overwrite

Languages
Languages
Languages
Python
Python
Python
Java
C++
C++
Bash
Ruby
Ruby
Destination
Source
15


### ELT (Extract, Load, Transform)

03


#### Selecting Streams and Sync Modes in Airbyte

[START_TABLE_CONTENT]
| Sync Mode | How It Works | When Records Are<br>Replaced | When It’s Useful |
| --- | --- | --- | --- |
| Incremental \| Append | Adds only new or<br>updated records (based<br>on a cursor). Does not<br>remove or overwrite<br>existing rows. | Never. Old rows remain;<br>new rows are appended<br>even if they refer to the<br>same primary key. | Keeping a full history of<br>changes, audit logs,<br>event-style data. |
| Full Refresh \| Overwrite | Rebuilds the entire table<br>on every sync by pulling<br>all source data. | Always. The destination<br>table is dropped and<br>rebuilt with the latest full<br>dataset. | Ensuring the destination<br>always matches the<br>source exactly; small<br>datasets; when no<br>incremental cursor<br>exists. |
[END_TABLE_CONTENT]
16


#### 03 ELT (Extract, Load, Transform)


##### Selecting Streams and Sync Modes in Airbyte

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_016_00.png|9cc255cc7b2a [END_IMAGE_PATH]
17


#### 03 ELT (Extract, Load, Transform)


##### Data Transformation

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_017_00.png|61406fef11a2 [END_IMAGE_PATH]
18


#### 03 ELT (Extract, Load, Transform)


##### Data Transformation

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_018_00.png|875acccd6552 [END_IMAGE_PATH]
19


#### 03 ELT (Extract, Load, Transform)


##### Data Transformation

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_019_00.png|61f084ad8f4e [END_IMAGE_PATH]
20
[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_020_00.png|7f7673ed7cc8 [END_IMAGE_PATH]


#### 03 ELT (Extract, Load, Transform)


##### Data Transformation

21
[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_021_00.png|7f7673ed7cc8 [END_IMAGE_PATH]


#### 03 ELT (Extract, Load, Transform)


##### Data Transformation

22


#### 03 ELT (Extract, Load, Transform)

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_022_00.png|b4057a6d0af5 [END_IMAGE_PATH]


##### Data Transformation

23


#### 04 Decision Support System Design

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_023_00.png|26bd332972ff [END_IMAGE_PATH]
Segmentation
result on
May 2014
24


#### 04 Decision Support System Design

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_024_00.png|4c3e2e357680 [END_IMAGE_PATH]
Figure: Playground Mode
25


#### 04 Some Example Insights

1. Resource Allocation: Efficiency vs Scale
The system separates high-efficiency markets from low-efficiency ones.
Segment 1 delivers $1.82M efficiently. Segment 5 requires 3 markets to match that output.
=> Action: Restructure Segment 5 to reduce overhead; expand Segment 2, which shows strong
revenue efficiency.
[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_025_00.png|d9b03c862644 [END_IMAGE_PATH]
26


#### 04 Some Example Insights

2.Product Strategy: Average unit price reveals two customer types:
Segment 1 operates as a Volume Leader (~$343).
Segments 2 and 5 form a Premium Niche (~$430 and ~$410).
=> Action: Loyalty programs for price-sensitive Segment 1; target premium upselling to Segments
2 and 5.
[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_026_00.png|d9b03c862644 [END_IMAGE_PATH]
27


#### 04 Some Example Insights

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_027_00.png|1d2d155c693b [END_IMAGE_PATH]
3. Market Behavior: LSTM trends expose growth
and seasonal patterns.
Segment
3
shows
the
strongest
momentum, growing from $324k to $1.35M.
Segments
1
and
4
exhibit
strong
seasonality.
=> Action: Invest in Segment 3 as a future
growth driver; align inventory and marketing
with seasonal spikes in Segments 1 and 4.
28


#### 04 Some Example Insights

[START_IMAGE_PATH] /Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_AI_SERVICE_FOLDER/backend/output/pdf_rag_ready/Data Warehouse/images/img_028_00.png|fd44c35130d2 [END_IMAGE_PATH]
29
Figure: AI Suggestion


#### 05 Conclusion

The Big Wins:
Speed: Insights arrive instantly after month-close, not days later.
Trajectory: We see who is growing and who is dying, preventing bad investments in declining
markets.
Scale: Cloud-native design handles 50 or 5,000 markets without breaking.
The Trade-off:
"Cold Start": The AI needs history to learn. Brand new markets can't be classified immediately
—but this protects us from "false start" investments.
AI hallucination problem.
What's Next?
Forecasting: Move from describing the past to predicting next month’s inventory needs.
Real-Time: Capture viral trends instantly instead of waiting for the monthly report.
30


## You.

For Your Attention
31
