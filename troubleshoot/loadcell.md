# Loadcell Troubleshooting

## Case Log: 29.05.2026
- **Issue**: Loadcell value flickers.
- **Measures Taken**:
  1. **Resoldered the IC**:
     - *Result*: Worked well in bench test using SMPS. But in simulator when the motor runs, it happened again.
  2. **Checked Schematic**:
     - Checked the schematic and saw that all components are in the ADC HX711. Found it was a capacitor issue.
     - *Action*: Added the capacitor.
     - *Result*: Worked successfully.
