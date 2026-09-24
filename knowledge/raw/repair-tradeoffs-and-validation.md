---
id: repair-tradeoffs-and-validation
title: Timing Repair Tradeoffs and Validation
topics: [setup, hold]
sources:
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Hold/Removal-Min-Delay-Analysis
  - https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Verifying-Timing-Signoff
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Consider-Pipelining-Up-Front
  - https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Avoid-Unnecessary-Pipelining
  - https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Determining-if-Hold-Fixing-is-Negatively-Impacting-the-Design
  - https://github.com/The-OpenROAD-Project/OpenSTA
---

# Timing Repair Tradeoffs and Validation

## Recheck both delay directions and all required corners

After a setup or hold change, rerun both maximum-delay and minimum-delay analysis. Vivado commonly finds setup problems at the slow corner and hold problems at the fast corner, but exceptions exist, especially at interfaces. AMD recommends both analysis directions at both corners; do not combine unrelated corners within one path calculation. A repair that improves one reported slack is incomplete until the other required checks have also passed. Source: [AMD UG906 corner coverage](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Hold/Removal-Min-Delay-Analysis).

## Preserve functional timing when adding latency

Late pipeline insertion can propagate latency differences throughout a circuit. For this project, a proposed RTL repair should therefore state whether cycle latency changes, identify dependent control and parallel paths, and define the corresponding functional checks before acceptance. Reset behavior, enable behavior, data ordering and valid alignment belong in those checks. These are project review criteria inferred from the architectural impact; this document contains no executed equivalence proof. Source: [AMD UG949 planning pipeline latency](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Consider-Pipelining-Up-Front).

## Resource cost and setup versus hold interaction

Extra pipeline stages increase register and routing demand, which can make a highly utilized FPGA harder to place and route. More stages are not automatically better. Source: [AMD UG949 unnecessary pipelining](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Avoid-Unnecessary-Pipelining).

Hold-fixing detours can worsen setup; evaluate the final route rather than assuming a local improvement guarantees closure. Source: [AMD UG906 hold-fixing impact](https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Determining-if-Hold-Fixing-is-Negatively-Impacting-the-Design).

| Candidate change | Intended benefit | Review before acceptance |
| --- | --- | --- |
| Pipeline an overlong stage | Less combinational work per cycle | Added latency, aligned controls, resource use |
| Add physical data delay | More minimum-delay margin | Setup slack after implementation |
| Change a clock constraint | Accurate analysis relationship | Evidence that the new constraint matches hardware |

The table is a project review aid, not a set of validated repairs.

## Signoff uses implemented timing evidence

In Vivado, review timing after placement and routing, using the post-implementation checkpoint and timing summary. A successful synthesis or behavioral simulation alone is not timing signoff. Record the implementation stage with every before/after result so that improvements are comparable. Source: [AMD UG906 timing signoff](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Verifying-Timing-Signoff).

## Reproduce an ASIC timing comparison

For an OpenSTA-based comparison, retain the exact netlist, Liberty libraries, SDC constraints and applicable parasitic or annotated-delay inputs. Record whether clocks are ideal or propagated. These supported inputs determine what is being analyzed; changing them between runs can invalidate a claimed repair comparison. The RAG module retrieves this guidance but does not execute STA or certify a repaired circuit. Source: [OpenSTA input formats and clock support](https://github.com/The-OpenROAD-Project/OpenSTA).
