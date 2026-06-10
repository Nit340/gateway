.. Build Command:
..     cd doc && .\make.bat simplepdf

7. Cloud Integration
====================

The **Cloud Connection Manager** handles outgoing data streaming. The gateway supports transmitting tag values and metadata over three protocol standards: MQTT, HTTP, and FTP.

7.1 Connection Selection Panel
------------------------------
The interface is split into a list view and a configuration panel:
- **Connections List (Left)**: Shows all defined data endpoints, grouped by protocol badges (MQTT, HTTP, FTP). An online/offline status dot indicates real-time socket health.
- **Connection Details (Right)**: Shows current message statistics:

  * *Messages*: Total number of successfully transmitted packets.
  * *Errors*: Count of failed connection attempts or rejected payloads.
  * *Last Sent*: Timestamp of the last data transaction.
  * *Latency*: Connection response time in milliseconds.
  * *Enabled Toggle*: Active/deactive state for the selected connection.
  * *Delete Button*: Removes the selected connection.

.. image:: _static/cloud_connections.png
   :align: center
   :width: 80%

7.2 Creating a Connection
-------------------------
Clicking **Add Connection** opens a modal wizard:

**Step 1: Protocol Selection**
Choose from the three supported outbound protocols.

**Step 2: Endpoint Configuration**
Fill in the credentials and path settings for the chosen protocol:
- **Common Details**: Connection Name.
- **MQTT Settings**: Broker Host address, Port (default 1883), Username, and Password.
- **HTTP Settings**: Target Endpoint URL, Method (POST or PUT), and API Authorization Token.
- **FTP / SFTP / FTPS Settings**: FTP Host, Port (default 21), Protocol selection (FTP, SFTP, or FTPS), Username, and Password.

.. image:: _static/cloud_add_connection.png
   :align: center
   :width: 80%

7.3 Publishing Tag Selection
----------------------------
Once a connection is configured, users define which tags to stream. Clicking **Add Tags** opens a selector modal containing two tabs:
- **Available Tags**: Lists all mapped field device tags.
- **Metadata**: Lists system parameters (CPU usage, memory allocation, network details).
- **Interactive Table**: Users can search and select tags, and **edit the transmission Data Type** directly within the modal table row before confirming selection.
- **Selected Count**: Tracks how many data points are mapped to this outbound stream.

.. image:: _static/cloud_pub_tags.png
   :align: center
   :width: 80%

7.4 Import & Export
-------------------
- **Exporting**: Allows downloading the entire cloud connection configuration in two formats:
  * *JSON Format*: Recommended for exporting and loading configuration on other gateways.
  * *CSV Format*: Spreadsheet compatible layout.
- **Importing**: Select a JSON or CSV file to upload and import configurations.
- **Save All**: Performs a global synchronize of all connection forms with the backend server. A full-page loader (*"Saving Cloud Configuration"*) blurs the UI until changes are saved.

.. image:: _static/cloud_import_export.png
   :align: center
   :width: 80%
