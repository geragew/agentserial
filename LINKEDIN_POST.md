# LinkedIn launch post

## Main version

What if every AI agent completes its task successfully, but the system as a
whole still fails?

That question led me to build **AgentSerial**, an open-source correctness checker
for the combined effects of AI agents running in parallel.

Two agents can make locally valid decisions and still exceed a shared budget,
double-book a resource, or leave the system in an invalid state. Traditional
logs tell us that each task completed. AgentSerial checks whether the global
result remains correct across every feasible execution order.

The project:

- imports JSONL histories and OpenTelemetry traces;
- validates system-wide rules declared as contracts;
- detects failures that depend on execution order;
- reduces a failure to the smallest understandable counterexample;
- generates standalone HTML evidence reports;
- provides both a CLI and an optional HTTP API with OpenAPI documentation;
- runs locally and deterministically, without an API key or another AI model.

I am releasing the first version as open source and would value feedback from
people working on agents, observability, distributed systems, and software
quality.

Repository: https://github.com/geragew/agentserial
Live demo: https://geragew.github.io/agentserial/

What kind of multi-agent failure would you want to catch before production?

#OpenSource #ArtificialIntelligence #AIAgents #Python #OpenTelemetry
#DistributedSystems #SoftwareEngineering #Observability

## Short version

Every agent reported success. The system still failed.

I built **AgentSerial** to find that class of problem. It replays parallel effect
histories, checks global contracts, and reveals the smallest counterexample that
explains a failure.

Open source. Local. Deterministic. CLI and HTTP API. No API key required.

Repository: https://github.com/geragew/agentserial

#OpenSource #AIAgents #Python #DistributedSystems #Observability

## Suggested carousel or video captions

1. Every agent succeeded. The system did not.
2. Execution order can change the global result.
3. AgentSerial tests feasible orders against a contract.
4. A complex failure becomes a small, explainable counterexample.
5. Open source, local, deterministic, and API-ready.

Use `media/agentserial-demo.webm` as the product demonstration and
`media/social-preview.png` as the cover image.
