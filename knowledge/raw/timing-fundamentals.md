---
id: timing-fundamentals
title: Timing Fundamentals for Setup and Hold
topics: [setup, hold]
sources:
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Setup/Recovery-Relationship
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Hold/Removal-Relationship
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Skew-Definition
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Clock-Uncertainty
  - https://github.com/The-OpenROAD-Project/OpenSTA
---

# Timing Fundamentals for Setup and Hold

## Setup checks limit late data

A setup check asks whether the latest data arrives early enough for the selected capture edge. The available interval is determined by launch and capture waveforms, clock insertion delays, uncertainty, and the destination register setup requirement. Negative setup slack means that the latest arrival misses the deadline. A long combinational path can cause this, but the clock relationship also matters. In compact notation, with data delay including launch clock-to-Q:

```text
Amax = launch_edge + launch_clock_delay + maximum_data_delay
Rsetup = capture_edge + capture_clock_delay - setup_time - setup_uncertainty
setup_slack = Rsetup - Amax
```

These are explanatory equations; use the tool report for edge selection and pessimism adjustments. Source: [AMD UG906 setup relationships](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Setup/Recovery-Relationship).

## Hold checks limit early data

A hold check asks whether new data can arrive too soon and disturb the value intended for capture. It uses the earliest data arrival and the relevant hold capture edge. Negative hold slack means that new data can arrive before the hold requirement expires. A short data path can therefore fail even when its setup slack is excellent. The hold edge pair must come from STA; it need not be the worst setup pair.

```text
Amin = launch_edge + launch_clock_delay + minimum_data_delay
Rhold = hold_capture_edge + capture_clock_delay + hold_time + hold_uncertainty
hold_slack = Amin - Rhold
```

Source: [AMD UG906 hold relationships](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Hold/Removal-Relationship).

## Clock skew and uncertainty are different

Clock skew is the capture clock insertion delay minus the launch clock insertion delay, measured from their common point. In a simple same-clock register path, later capture clock arrival provides more setup time but demands more minimum data delay for hold. This sign interpretation is derived from the preceding slack equations. Do not identify every timing failure as excess combinational logic. Source: [AMD UG906 skew definition](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Skew-Definition).

Uncertainty describes timing variation and margins, including jitter and phase error. It is not another name for measured insertion skew. Vivado adds user uncertainty to its own calculation, with tool-specific exceptions for dedicated routing. Inspect the uncertainty actually reported before changing it. Source: [AMD UG906 clock uncertainty](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Clock-Uncertainty).

## STA evidence includes more than RTL

RTL expresses functionality; a timing result also depends on implementation and analysis inputs. In an ASIC flow, OpenSTA consumes a gate-level Verilog netlist, Liberty timing libraries and SDC constraints, with SDF or SPEF supplying delay or parasitic information as applicable. It supports ideal and propagated clocks. Record these inputs with a failing path so that a later comparison uses a consistent analysis context. Source: [OpenSTA project documentation](https://github.com/The-OpenROAD-Project/OpenSTA).
