# Prior Art

AgentSerial does not claim to invent serializability, concurrency control, or
transactional execution for agents. Its intended contribution is narrower: a
small, standalone, runtime-independent checker that classifies recorded agent
effect histories against explicit contracts and reduces counterexamples.

## Adjacent systems and research

### Jepsen and Elle

Jepsen tests distributed systems against explicit consistency models and reduces
failures to evidence. Elle checks transactional histories using dependency
graphs. AgentSerial borrows the discipline of precise histories and honest model
names, but v0.1 does not inject faults, run workloads, or implement established
database consistency models.

- https://jepsen.io/
- https://github.com/jepsen-io/elle

### CoAgent

"CoAgent: Concurrency Control for Multi-Agent Systems" proposes runtime
concurrency control with a predetermined order, speculative writes, repair, and
undoable tools. AgentSerial is post-hoc and runtime-independent; it neither
controls agents nor delegates correctness decisions to an LLM.

- https://arxiv.org/abs/2606.15376

### Agentic Transaction

"Agentic Transaction: Towards ACID-Compliant Agent Systems" adapts transactional
guarantees to long-horizon agents. AgentSerial does not claim ACID semantics and
checks a much smaller explicit state/effect model.

- https://arxiv.org/abs/2608.13900

### Invariant confluence

Invariant confluence studies when coordination-free execution can preserve
application invariants. It is directly relevant to future analysis of whether
all permitted schedules are safe. AgentSerial v0.1 uses exhaustive replay rather
than a general confluence decision procedure.

- https://www.vldb.org/pvldb/vol8/p185-bailis.pdf

## Positioning constraint

The phrases "first agent serializability checker", "formal verification", and
"Jepsen for agents" must not be presented as literal technical claims. "Inspired
by history-based distributed-systems checking" is defensible. This document
should grow with every materially overlapping project discovered.

