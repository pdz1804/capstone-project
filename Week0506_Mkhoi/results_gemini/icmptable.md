| Section                         | Bit 0-7                | Bit 8-15        | Bit 16-23        | Bit 24-31 |
| :------------------------------ | :--------------------- | :-------------- | :--------------- | :-------- |
| **IP Header (20 bytes)**  |                        |                 |                  |           |
|                                 | Version/IHL            | Type of Service | Length           |           |
|                                 | Identification         |                 | Flags and Offset |           |
|                                 | Time to Live           | Protocol        | Checksum         |           |
|                                 | Source IP Address      |                 |                  |           |
|                                 | Destination IP Address |                 |                  |           |
| **ICMP Header (8 bytes)** |                        |                 |                  |           |
|                                 | Type=8                 | Code=0          | Checksum         |           |
|                                 | Identifier             |                 | Sequence Number  |           |
| **Data (x+ bytes)**       | Data... (timestamp)    |                 |                  |           |
