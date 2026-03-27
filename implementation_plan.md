# Multi-Loadcell Configuration Refinement

This plan addresses the requirement to support multiple loadcell configurations. It involves adding a "Save" button for database-only updates, renaming the existing "Save Filters & Levels" to "Send", and ensuring the pipeline receives configurations for all enabled loadcells when sent.

## User Review Required

> [!IMPORTANT]
> The current backend implementation uses `LIMIT 1` when building loadcell configurations. This will be updated to include all enabled loadcell devices in the `load_cells` array sent to the pipeline.

## Proposed Changes

### Frontend Improvements

#### [MODIFY] [craneiq.html](file:///c:/Users/naresh kumar/Desktop/gateway/frontend/pages/craneiq.html)
- **Button Renaming**: Rename "Save Filters & Levels" to "Send to Pipeline".
- **New Button**: Add a "Save to Database" button that appears when more than one loadcell is present.
- **Status Display**: Update status text to show "Sending to the loadcell..." during transmission and a concise "Sent" or "Saved" on completion.

#### [MODIFY] [craneiq.js](file:///c:/Users/naresh kumar/Desktop/gateway/frontend/pages/js/craneiq.js)
- **[saveLoadcellFilters(saveOnly)](file:///c:/Users/naresh%20kumar/Desktop/gateway/frontend/pages/js/craneiq.js#392-479)**: Update this function to accept a `save_only` flag.
- **Conditional Logic**: If `save_only` is true, call the API with a flag that prevents the config from being sent to the pipeline immediately.
- **UI Logic**: Update the "Save" and "Send" button states and labels during the process.

### Backend Enhancements

#### [MODIFY] [pipeline.py](file:///c:/Users/naresh kumar/Desktop/gateway/flask/pipeline.py)
- **[pipeline_filters_post_handler](file:///c:/Users/naresh%20kumar/Desktop/gateway/flask/pipeline.py#1918-2166)**: 
    - Accept a `save_only` boolean in the request body.
    - If `save_only` is true, return after updating the DB.
    - If `save_only` is false (default), fetch **all** enabled loadcells and build a multi-device config for the pipeline.
- **[send_loadcell_config_now](file:///c:/Users/naresh%20kumar/Desktop/gateway/flask/pipeline.py#1722-1916)**:
    - Update query to fetch all rows from [loadcell_device](file:///c:/Users/naresh%20kumar/Desktop/gateway/flask/pipeline.py#1399-1432) where `enabled = 1`.
    - Build the `load_cells` array in the JSON config by iterating over all fetched devices.

## JSON Configuration Sample

When multiple loadcells are present, the config sent to the pipeline will look like this:

```json
{
  "version": 2,
  "send_version": 42,
  "load_cells": [
    {
      "name": "LoadCell_01",
      "device": { ... },
      "filter": { "raw": [...], "weight": [...] },
      "levels": { ... }
    },
    {
      "name": "LoadCell_02",
      "device": { ... },
      "filter": { "raw": [...], "weight": [...] },
      "levels": { ... }
    }
  ],
  "ipc": [...],
  "logging": [...]
}
```

## Verification Plan

### Automated Tests
- N/A (Manual UI verification required)

### Manual Verification
1.  **Single Loadcell**:
    - Verify "Send" button works and updates the pipeline.
    - Verify "Save" button is hidden.
2.  **Two Loadcells**:
    - Verify "Save" button is visible.
    - Click "Save" on Device A, then switch to Device B and back. Verify changes to Device A are persisted in the UI (re-populated from DB).
    - Click "Send". Verify (via logs) that both loadcells are included in the JSON payload sent to the pipeline.
    - Verify the "Send" button shows "Sent to Pipeline" and then reverts.
