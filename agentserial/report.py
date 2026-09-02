from __future__ import annotations

from html import escape

import yaml

from agentserial.models import CheckResult, Contract, History, Operation, VerdictStatus


def generate_report(history: History, contract: Contract, result: CheckResult) -> str:
    status_class = _status_class(result.status)
    safe_order = " → ".join(result.safe_witness.order) if result.safe_witness else "No safe witness"
    unsafe_order = " → ".join(result.unsafe_witness.order) if result.unsafe_witness else "No unsafe witness"
    violations = result.unsafe_witness.violations if result.unsafe_witness else result.read_conflicts
    counterexample = result.counterexample_operations
    contract_yaml = yaml.safe_dump(contract.model_dump(mode="json"), sort_keys=False, allow_unicode=False)
    rows = "".join(
        f"<tr><td>{index:02d}</td><td>{escape(operation.agent)}</td><td>{escape(operation.id)}</td>"
        f"<td>{len(operation.reads):02d}</td><td>{len(operation.effects):02d}</td>"
        f"<td class='ok'>{escape(operation.status.upper())}</td></tr>"
        for index, operation in enumerate(history.operations, start=1)
    )
    counter_rows = (
        "".join(
            f"<div class='counter-row'><b>{index:02d}</b><span>{escape(operation.agent)}</span>"
            f"<strong>{escape(operation.id)}</strong><code>{escape(_operation_summary(operation))}</code></div>"
            for index, operation in enumerate(counterexample, start=1)
        )
        or "<p class='empty'>No reduced counterexample for this verdict.</p>"
    )
    diagnostics = (
        "".join(f"<li>{escape(item)}</li>" for item in violations) or "<li>No violation diagnostic.</li>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgentSerial report — {escape(history.history_id)}</title><style>
:root{{--bg:#eef0ed;--surface:#f8f9f6;--alt:#e7e9e5;--border:#c7cbc4;--text:#191c19;--muted:#686e67;--accent:#b77818;--danger:#a13d32;--success:#3f6c52;--mono:"Cascadia Code",Consolas,monospace;--sans:"Segoe UI",Arial,sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px var(--sans)}}header{{height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 25px;background:var(--surface);border-bottom:1px solid #979d94}}.brand{{display:flex;align-items:center;gap:10px;font-weight:700}}.mark{{width:25px;height:25px}}.mark path{{fill:none;stroke:currentColor;stroke-width:1.8}}.mark .x{{stroke:var(--accent);stroke-width:3}}header small{{font:9px var(--mono);color:var(--muted)}}main{{max-width:1220px;margin:0 auto;background:var(--surface);min-height:calc(100vh - 54px);border-inline:1px solid var(--border)}}.run{{display:grid;grid-template-columns:1fr auto;gap:30px;padding:26px;border-bottom:1px solid #979d94}}.label{{color:var(--muted);font:700 9px var(--mono);letter-spacing:.1em}}h1{{margin:8px 0 0;font-size:26px}}.verdict{{display:grid;align-content:center;justify-items:end}}.verdict strong{{margin-top:7px;font:700 17px var(--mono)}}.verdict .fail{{color:var(--danger)}}.verdict .warn{{color:var(--accent)}}.verdict .pass{{color:var(--success)}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);background:var(--alt);border-bottom:1px solid #979d94}}.metrics div{{padding:17px 20px;border-right:1px solid var(--border)}}.metrics div:last-child{{border:0}}.metrics span{{display:block;color:var(--muted);font:8px var(--mono)}}.metrics b{{display:block;margin-top:7px;font:16px var(--mono)}}.grid{{display:grid;grid-template-columns:1.35fr .65fr;border-bottom:1px solid #979d94}}section{{min-width:0}}.section-head{{padding:15px 20px;border-bottom:1px solid var(--border);font:700 9px var(--mono);letter-spacing:.09em}}table{{width:100%;border-collapse:collapse;font:10px var(--mono)}}th,td{{height:43px;padding:0 14px;border-bottom:1px solid var(--border);text-align:left}}th{{height:34px;background:var(--alt);color:var(--muted);font-size:8px}}.ok{{color:var(--success);font-weight:700}}.evidence{{padding:20px;border-left:1px solid #979d94}}.evidence h2{{margin:10px 0 22px;font:18px var(--mono)}}.witness{{padding:13px 0;border-top:1px solid var(--border)}}.witness span{{display:block;color:var(--muted);font:8px var(--mono)}}.witness code{{display:block;margin-top:8px;font-size:10px}}.evidence ul{{padding-left:17px;color:var(--danger);font:10px/1.6 var(--mono)}}.lower{{display:grid;grid-template-columns:1fr 420px}}.counter{{border-right:1px solid #979d94}}.counter-row{{display:grid;grid-template-columns:38px 100px 150px 1fr;align-items:center;min-height:55px;padding:0 20px;border-bottom:1px solid var(--border);font:10px var(--mono)}}.counter-row b{{color:var(--accent)}}.counter-row span{{color:var(--muted)}}.counter-row code{{text-align:right}}.contract pre{{margin:0;padding:20px;overflow:auto;background:#20231f;color:#dce0da;font:10px/1.7 var(--mono)}}.empty{{padding:20px;color:var(--muted)}}@media(max-width:800px){{main{{border:0}}.metrics{{grid-template-columns:repeat(2,1fr)}}.grid,.lower{{grid-template-columns:1fr}}.evidence,.counter{{border:0;border-top:1px solid #979d94}}.run{{grid-template-columns:1fr}}.verdict{{justify-items:start}}}}
</style></head><body>
<header><div class="brand"><svg class="mark" viewBox="0 0 32 32"><path d="M3 7h8l5 7 5-7h8M3 25h8l5-7 5 7h8"/><path class="x" d="M13 16h6"/></svg>AgentSerial</div><small>LOCAL REPORT / v0.6.0</small></header>
<main><div class="run"><div><span class="label">HISTORY / {escape(history.history_id)}</span><h1>Contract replay classification</h1></div><div class="verdict"><span class="label">VERDICT</span><strong class="{status_class}">{result.status.value}</strong></div></div>
<div class="metrics"><div><span>AGENTS</span><b>{result.agents:02d}</b></div><div><span>OPERATIONS</span><b>{result.operations:02d}</b></div><div><span>FEASIBLE</span><b>{result.feasible_replays:02d}</b></div><div><span>SAFE</span><b>{result.safe_replays:02d}</b></div><div><span>UNSAFE</span><b>{result.unsafe_replays:02d}</b></div></div>
<div class="grid"><section><div class="section-head">EXECUTION HISTORY</div><table><thead><tr><th>#</th><th>AGENT</th><th>OPERATION</th><th>READS</th><th>EFFECTS</th><th>STATUS</th></tr></thead><tbody>{rows}</tbody></table></section><aside class="evidence"><span class="label">REPLAY EVIDENCE</span><h2>{result.status.value}</h2><div class="witness"><span>SAFE WITNESS</span><code>{escape(safe_order)}</code></div><div class="witness"><span>UNSAFE WITNESS</span><code>{escape(unsafe_order)}</code></div><ul>{diagnostics}</ul></aside></div>
<div class="lower"><section class="counter"><div class="section-head">1-MINIMAL REDUCED COUNTEREXAMPLE</div>{counter_rows}</section><section class="contract"><div class="section-head">GLOBAL CONTRACT</div><pre>{escape(contract_yaml)}</pre></section></div>
</main></body></html>"""


def _status_class(status: VerdictStatus) -> str:
    match status:
        case VerdictStatus.ROBUST_PASS:
            return "pass"
        case VerdictStatus.SCHEDULE_DEPENDENT | VerdictStatus.INCONCLUSIVE:
            return "warn"
        case _:
            return "fail"


def _operation_summary(operation: Operation) -> str:
    reads = operation.reads
    effects = operation.effects
    if effects:
        effect = effects[0]
        return f"{effect.type} {effect.resource} {effect.value!r}"
    if reads:
        read = reads[0]
        return f"read {read.resource}={read.value!r}@v{read.version}"
    return "no modeled effect"
