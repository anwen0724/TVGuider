---
id: hold-repair
title: Hold Repair Strategies and Preconditions
topics: [hold]
sources:
  - https://openroad.readthedocs.io/en/latest/main/src/rsz/README.html
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Fixing-Large-Hold-Violations-Prior-to-Routing
  - https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Multicycle-Paths
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Hold/Removal-Relationship
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Pipelining-Considerations
---

# Hold Repair Strategies and Preconditions

## ASIC delay insertion after clock tree synthesis

OpenROAD `repair_timing -hold` performs physical hold repair after clock tree synthesis with propagated clocks. Added buffers can increase minimum data-path delay, but they also consume setup margin. By default, the resizer avoids buffer insertions that create setup violations; `-allow_setup_violations` explicitly relaxes this protection. Its setup pass precedes its hold pass. These rules apply to OpenROAD physical implementation, not directly to FPGA RTL. Source: [OpenROAD gate resizer](https://openroad.readthedocs.io/en/latest/main/src/rsz/README.html).

## FPGA physical hold optimization

Vivado can repair large hold violations before routing after clock-tree constraints are checked. `phys_opt_design -hold_fix` inserts LUT1 delay on selected severe paths with sufficient setup slack; `-aggressive_hold_fix` considers more paths and uses additional LUT resources. Routing can then repair remaining smaller violations with detours. Tool-supported physical insertion is distinct from assuming arbitrary RTL statements will provide a controlled physical delay. Source: [AMD UG949 pre-route hold repair](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Fixing-Large-Hold-Violations-Prior-to-Routing).

## Correct an erroneous hold relationship

If the violation comes from a misrepresented multicycle transfer, correct the constraints to match the real launch and capture enable behavior. Examine both setup and hold relationships after the change. A hold exception must express design intent; it cannot be used simply to hide an actually unsafe short path. Source: [AMD UG903 multicycle paths](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Multicycle-Paths).

## Why lowering frequency usually does not fix same-edge hold

For a same-clock, same-edge hold check, the relevant launch and capture edges coincide. Increasing the clock period does not directly change their separation or add minimum data-path delay. This follows from the hold slack equation. A different edge relationship or clock reconfiguration must be reanalyzed explicitly; a slower clock alone is not a general hold repair. Source: [AMD UG906 hold relationships](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Hold/Removal-Relationship).

## Register insertion needs a sequential behavior review

Adding an ordinary pipeline register changes cycle latency and is not a generic substitute for physical hold buffering. A specialized Vivado optimization can insert negative-edge flip-flops on eligible paths, splitting the path into half-period segments, and rejects the change if setup slack is insufficient. Such an implementation transformation has specific preconditions; do not generalize it to arbitrary RTL register insertion. Sources: [AMD UG949 pre-route hold repair](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Fixing-Large-Hold-Violations-Prior-to-Routing), [pipeline latency](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Pipelining-Considerations).
