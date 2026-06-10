# Univa IoT Gateway - Troubleshooting Guide

Use the flowchart below to navigate to the correct troubleshooting logs:

```mermaid
graph TD
    Start([Troubleshooting Start]) --> Choice{Identify the Issue}
    Choice -->|Loadcell Value Flicker| LC_Page[Loadcell Troubleshooting]
    Choice -->|Random Reboots| RB_Page[Reboot Troubleshooting]

    click LC_Page href "./loadcell.md" "View Loadcell Troubleshooting"
    click RB_Page href "./reboot.md" "View Reboot Troubleshooting"
```

## Available Logs
- [Loadcell Troubleshooting](loadcell.md)
- [Reboot Troubleshooting](reboot.md)
