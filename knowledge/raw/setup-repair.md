---
id: setup-repair
title: Setup Repair Strategies and Preconditions
topics: [setup]
sources:
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Pipelining-Considerations
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Check-Inferred-Logic
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Replicate-High-Fanout-Net-Drivers
  - https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Multicycle-Paths
  - https://openroad.readthedocs.io/en/latest/main/src/rsz/README.html
---

# Setup Repair Strategies and Preconditions

## Pipeline only with an accepted latency contract

Splitting a long datapath across registered stages can raise the achievable clock frequency. It also adds cycle latency and control overhead. Before changing RTL, specify the new latency and align accompanying valid, enable, and sideband signals with the data; these alignment checks are engineering consequences of the changed interface timing. An extra register is not automatically a cycle-equivalent repair. The caller must permit the new behavior. Source: [AMD UG949 pipelining considerations](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Pipelining-Considerations).

## Retiming and dedicated register resources

Retiming moves registers across combinational logic to redistribute delay. Vivado offers synthesis retiming and directed retiming attributes, while RAM and arithmetic inference may benefit from appropriate register placement. Inspect the resulting netlist and retain the intended reset, enable, and observable sequential behavior. This is a candidate transformation, not a guarantee that a particular path will improve. Source: [AMD UG949 inferred logic and retiming](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Check-Inferred-Logic).

## Replicate a timing-critical high-fanout driver

For a normal synchronous data or control net, register replication can divide the loads among nearby drivers and reduce routing pressure. Select the critical net and meaningful load groups. A global fanout threshold may duplicate many irrelevant registers and increase utilization or power. In AMD flows, physical optimization can use actual placement information; excessive preservation properties can prevent further improvement. Source: [AMD UG949 register replication](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Replicate-High-Fanout-Net-Drivers).

## ASIC cell and load optimization

In OpenROAD, setup repair can use sizing, threshold-voltage changes, pin swapping, buffering, cloning and load splitting. These are technology-mapped netlist operations, requiring the relevant libraries and physical context. `repair_design` also handles slew, capacitance and fanout constraints. An RTL-only repair module should not claim it has performed these physical changes. Source: [OpenROAD gate resizer](https://openroad.readthedocs.io/en/latest/main/src/rsz/README.html).

## Multicycle constraints require real functional intent

A multicycle exception changes the edge relationship used for analysis. Apply it only when launch and capture control genuinely permits data to take multiple cycles. Inspect the associated hold relationship as well. Relaxing a single-cycle path merely to remove negative slack does not repair the hardware. Source: [AMD UG903 multicycle paths](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Multicycle-Paths).
