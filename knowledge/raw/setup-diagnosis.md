---
id: setup-diagnosis
title: Diagnosing Setup Timing Violations
topics: [setup]
sources:
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Determine-Whether-Pipelining-is-Needed
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Check-Inferred-Logic
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Category-3-Physical
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Setup/Recovery-Max-Delay-Analysis
  - https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Determining-if-Hold-Fixing-is-Negatively-Impacting-the-Design
---

# Diagnosing Setup Timing Violations

## Deep logic and unbalanced combinational stages

Inspect the logic depth between the reported startpoint and endpoint and compare it with the target frequency. Several arithmetic or selection operations may have been placed in a single cycle, while adjacent stages do little work. In Vivado, `report_design_analysis -logic_level_distribution` helps locate these unusually deep paths. A pipeline proposal should partition the actual critical logic into balanced stages rather than merely add a register at an already short boundary. Source: [AMD UG949 pipeline assessment](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Determine-Whether-Pipelining-is-Needed).

## Dedicated block and inference bottlenecks

Examine what synthesis inferred from the RTL. A large fan-in cone, unregistered block RAM output, insufficiently pipelined arithmetic, or a large XOR function can create a setup bottleneck. Dedicated blocks may have significant clock-to-output or setup requirements. The number of RTL statements is not a measure of physical logic depth. Use the synthesized path and resource mapping to choose the repair location. Source: [AMD UG949 inferred logic checks](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Check-Inferred-Logic).

## Routing, fanout, and placement restrictions

A path with few logic levels can still fail setup because net delay dominates. In AMD devices, inspect high fanout, large placement distances, SLR crossings, architectural column crossings, and restrictive Pblocks. Excessive floorplanning can prevent useful placement changes. If replication fails to occur, inspect preservation properties such as `DONT_TOUCH` or `MARK_DEBUG`. Diagnose the physical cause before adding latency to the RTL. Source: [AMD UG906 physical path characteristics](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Category-3-Physical).

## Setup regression after routing

If setup passed after placement but failed after routing, check whether the router inserted detours to satisfy hold. In Vivado, `report_design_analysis -show_all` exposes the Hold Fix Detour information. Review the minimum-delay check on the same path, excessive clock skew, and incomplete multicycle constraints. The longer routed path can be a consequence of a hold problem. Source: [AMD UG906 hold-fixing impact](https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Determining-if-Hold-Fixing-is-Negatively-Impacting-the-Design).

## Maximum-delay analysis context

Record the corner and analysis type alongside the setup slack. Vivado evaluates maximum-delay timing using slow launch-clock and data delays together with fast capture-clock delay within the selected corner. It performs such analysis at both device corners. A timing number from an estimated or differently configured run is not automatically comparable to a routed signoff number. Source: [AMD UG906 maximum-delay analysis](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Setup/Recovery-Max-Delay-Analysis).
