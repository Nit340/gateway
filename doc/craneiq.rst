8. CraneIQ Pro Configuration
============================

The **CraneIQ Pro** module manages specialized safety logic, data logging buffers, and crane profiles on the gateway.

In this version, the configuration interface supports the Load Cell Pipeline & Calibration utility. Additional crane intelligence features are scheduled for the next release (r002).

8.1 Load Cell Pipeline & Calibration
------------------------------------
Manages real-time load sensor data streams, calibration parameters, and filters.

**Pipeline Connection**
Users click **Connect** to initialize the load cell data pipeline. Once active:
- The status indicator switches to *Connected* (green dot).
- The **Live Bar** displays real-time readings:

  * *Raw Value*: Left panel displaying raw ADC counts.
  * *Live Weight*: Right panel displaying calibrated weight.

- **Raw Toggle**: Enables/disables the raw load whitelist in the parser pipeline.
- **Calibrate**: Opens a calibration modal to perform tare adjustments:

  * *Zero State (Tare)*: Capture zero state.
  * *Known Weight*: Capture raw reading at a specified test weight.
  * *Save*: Commits offsets to the gateway driver.

**Signal Filters**
To eliminate electrical noise and mechanical sway, users can create two chains of signal filters:
1. **Raw Signal Filters**: Filters raw digital data before weight translation.
2. **Weight Filters**: Filters final weight values.
- *Available Filters*: Median, Moving Average, Kalman, Adaptive Deadband, Low Pass, Notch Filter, and Hysteresis Quantizer.
- *Interactive Ordering*: Drag-and-drop handles enable custom filter sequencing.

**Load Levels**
Set safety trip levels as a percentage (0.0 to 1.0) of maximum capacity:
- **Low**: Minimum weight threshold.
- **Normal**: Safe operation margin.
- **High**: Approaching load limits.

.. image:: _static/craneiq_loadcell.png
   :align: center
   :width: 80%

8.2 Planned Features for Release r002
-------------------------------------
The following features are scheduled to be added in the upcoming **r002** release:

- **Crane Profile & Overview**: Establish the physical profile of the monitored asset, including crane type, maximum capacity, operating mode, dimensional attributes, and map layer uploads for zoning.
- **Data Buffer / Datalogger**: Configures localized buffering to prevent data loss during network outages, featuring priority hierarchy, sample formatting, and storage allocation settings.
- **Safety Systems**: Configuration parameters for anti-collision logic (LiDAR/Radar sensors) and restricted zoning boundary actions.
- **Health & Load Intelligence**: Thermal monitoring for LT/CT/MH hoist motors, and structural wear monitoring (brake coil current, release time, and slippage detection).
- **Auto-Generated Rules**: View-only panel listing active safety rules automatically compiled from configuration parameters (e.g., Load Limiter, Motor Overheat, and Zone Violation).
