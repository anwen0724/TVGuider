---
id: hold-diagnosis
title: Diagnosing Hold Timing Violations
topics: [hold]
sources:
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Min-Delay-with-Hold-and-Removal-Checks
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Skew-Definition
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Clock-Uncertainty
  - https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Input-Delay
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/No-Input/Output-Delays-and-Partial-Input/Output-Delays
  - https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Determining-if-Hold-Fixing-is-Negatively-Impacting-the-Design
---

# Diagnosing Hold Timing Violations

## Short paths and earliest arrival

Inspect minimum-delay timing, not just the longest combinational path. A direct register connection or a path with little logic may allow new data to arrive too early. Vivado hold analysis combines early launch-clock and data delays with late capture-clock delay within one corner. A successful maximum-delay report therefore cannot establish hold safety. Source: [AMD UG906 minimum-delay checks](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Min-Delay-with-Hold-and-Removal-Checks).

## Late capture clock and excessive skew

Compare launch and capture clock insertion delays from their common point. If the capture clock arrives later, the receiving register needs the old data to remain stable longer in absolute time. For a same-edge path this consumes hold margin. Trace the clock paths as well as the data path; short RTL logic alone does not establish the root cause. This interpretation combines the skew definition with the hold equation. Source: [AMD UG906 skew definition](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Skew-Definition).

## Unexpected hold requirement after a multicycle exception

A surprisingly large hold requirement can come from an incomplete `set_multicycle_path` specification, particularly a setup change without the intended hold adjustment. Review the selected edge pair and constraint coverage before requesting additional data delay. Large skew is another cause of difficult hold closure. Source: [AMD UG906 hold-fixing impact](https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Determining-if-Hold-Fixing-is-Negatively-Impacting-the-Design).

## Uncertainty in the actual hold report

Check how much uncertainty the timing engine applied and where it originated. In Vivado, user uncertainty and computed clock variation are separate contributions. Dedicated intra-clock routing has special hold handling, so use the reported value rather than blindly applying a generic margin. Removing justified uncertainty changes the model, not the physical path. Source: [AMD UG906 clock uncertainty](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Clock-Uncertainty).

## Input interface and board timing assumptions

For an input-to-register failure, inspect the external data arrival relative to the reference clock. An input delay represents board and external-device timing at the FPGA interface and may be positive or negative. Verify the earliest-arrival assumptions used for hold against that interface, rather than treating an internal register-to-register explanation as sufficient. Source: [AMD UG903 input delay](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Input-Delay).

Missing or partial I/O constraints also require review: a clean internal report does not prove the external interface has been checked. Source: [AMD UG949 I/O constraint coverage](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/No-Input/Output-Delays-and-Partial-Input/Output-Delays).
