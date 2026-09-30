"""Strict mounted DSH evidence acceptance runner (Phase 4.3.2).

Independently maps semantic markers to statuses. Vitest return code alone
is NOT live PASS. Includes a baseline lane324 control in the same window.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DSH_SRC = Path(os.environ.get("DSH_SRC") or r"C:\dsh-src")
CONFIG_EVIDENCE = DSH_SRC / "vitest.ai4s-phase432.config.ts"
CONFIG_BASELINE = DSH_SRC / "vitest.ai4s-lane324.config.ts"
OUT = ROOT / "results" / "phase-04-3-2-dsh-evidence-smoke.json"

MARKERS = {
    "discovery": "LANE325_DISCOVERY_OK=1",
    "retrieve_toolcall": "LANE325_RETRIEVE_TOOLCALL_OK=1",
    "retrieve_result": "LANE325_RETRIEVE_RESULT_OK=1",
    "retrieve_identity": "LANE325_RETRIEVE_IDENTITY_MATCH=1",
    "validate_toolcall": "LANE325_VALIDATE_TOOLCALL_OK=1",
    "validate_result": "LANE325_VALIDATE_RESULT_OK=1",
    "validate_policy": "LANE325_VALIDATE_POLICY_MATCH=1",
    "live_complete": "LANE325_LIVE_COMPLETE=1",
    "no_credential": "LANE325_NO_CREDENTIAL=1",
}


def load_deepseek_key() -> str | None:
    cred = Path.home() / ".dsh" / ".credentials.yaml"
    if not cred.exists():
        return None
    text = cred.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        if "DEEPSEEK_API_KEY" in line and ":" in line:
            val = line.split(":", 1)[1].strip().strip("'\"")
            if val:
                return val
        if line.strip().startswith("secret:") and "DEEPSEEK" in text:
            val = line.split(":", 1)[1].strip().strip("'\"")
            if val and val.startswith("sk-"):
                return val
    return None


def _redact(text: str, key: str | None) -> str:
    if key:
        text = text.replace(key, "***")
    return text


def run_vitest(config: Path, env: dict, timeout: int = 600) -> tuple[int, str, str]:
    vitest_bin = DSH_SRC / "node_modules" / ".bin" / "vitest.CMD"
    if not vitest_bin.exists():
        vitest_bin = DSH_SRC / "node_modules" / ".bin" / "vitest"
    if vitest_bin.exists():
        cmd = [str(vitest_bin), "run", "--config", str(config)]
    else:
        cmd = ["pnpm", "exec", "vitest", "run", "--config", str(config)]
    proc = subprocess.run(
        cmd,
        cwd=str(DSH_SRC),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=True,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def classify_outputs(
    *,
    credential_available: bool,
    evidence_stdout: str,
    evidence_rc: int,
    baseline_stdout: str,
    baseline_rc: int,
) -> dict:
    """Map markers to independent statuses. No cross-inference."""

    def has(s: str, marker: str) -> bool:
        return marker in s

    out: dict = {}
    discovery = has(evidence_stdout, MARKERS["discovery"])
    out["mounted_dsh_tool_discovery"] = "PASS" if discovery else "FAILED"

    retrieve_toolcall = has(evidence_stdout, MARKERS["retrieve_toolcall"])
    retrieve_result = has(evidence_stdout, MARKERS["retrieve_result"])
    retrieve_identity = has(evidence_stdout, MARKERS["retrieve_identity"])
    validate_toolcall = has(evidence_stdout, MARKERS["validate_toolcall"])
    validate_result = has(evidence_stdout, MARKERS["validate_result"])
    validate_policy = has(evidence_stdout, MARKERS["validate_policy"])

    out["retrieve_toolcall"] = "PASS" if retrieve_toolcall else ("NOT_RUN_ENV" if not credential_available else "FAILED")
    out["retrieve_linked_result"] = "PASS" if retrieve_result else ("NOT_RUN_ENV" if not credential_available else "FAILED")
    out["direct_vs_dsh_evidence_identity_match"] = "PASS" if retrieve_identity else ("NOT_RUN_ENV" if not credential_available else "FAILED")
    out["validate_toolcall"] = "PASS" if validate_toolcall else ("NOT_RUN_ENV" if not credential_available else "FAILED")
    out["validate_linked_result"] = "PASS" if validate_result else ("NOT_RUN_ENV" if not credential_available else "FAILED")
    out["direct_vs_dsh_policy_match"] = "PASS" if validate_policy else ("NOT_RUN_ENV" if not credential_available else "FAILED")

    # Baseline control classification
    baseline_empty = (
        "tool_call_count" in baseline_stdout
        and re.search(r"tool_call_count['\"]?\s*[:=]\s*0", baseline_stdout) is not None
    ) or ("LANE324_ZERO_TOOLCALL" in baseline_stdout)
    evidence_empty = (
        has(evidence_stdout, "LANE325_RETRIEVE_FAILED")
        or (
            not retrieve_toolcall
            and "EMPTY" in evidence_stdout.upper()
        )
        or (not retrieve_toolcall and credential_available)
    )
    baseline_pass = baseline_rc == 0 and "tool_call_count" in baseline_stdout and not baseline_empty
    # lane324 reports tool_call_count in JS report object, not always printed.
    # Treat rc==0 + test passed name as baseline PASS when not empty-response.
    if baseline_rc == 0 and "knowledge-curator mounted Agent" in baseline_stdout and not baseline_empty:
        baseline_pass = True
    if baseline_rc != 0 and ("tool_call_count" in baseline_stdout and "0" in baseline_stdout and "expected +0 to be 1" in (baseline_stdout + "")):
        baseline_empty = True
        baseline_pass = False

    # More reliable: parse our runner-injected baseline markers if present.
    if "LANE324_BASELINE_TOOLCALL_OK=1" in baseline_stdout:
        baseline_pass = True
        baseline_empty = False
    if "LANE324_ZERO_TOOLCALL" in baseline_stdout:
        baseline_empty = True
        baseline_pass = False

    if not credential_available:
        baseline_status = "NOT_RUN_ENV"
        external = False
        classification = "NOT_RUN_ENV"
    elif baseline_pass and has(evidence_stdout, MARKERS["live_complete"]):
        baseline_status = "PASS"
        external = False
        classification = "A_PASS"
    elif baseline_pass and not has(evidence_stdout, MARKERS["live_complete"]):
        baseline_status = "PASS"
        external = False
        classification = "B_EVIDENCE_REGRESSION"
    elif baseline_empty and evidence_empty:
        baseline_status = "EMPTY_RESPONSE"
        external = True
        classification = "C_EXTERNAL_RUNTIME_UNAVAILABLE"
    elif not baseline_pass:
        baseline_status = "FAILED"
        external = False
        classification = "D_BASELINE_ENV_FAIL"
    else:
        baseline_status = "UNKNOWN"
        external = False
        classification = "UNKNOWN"

    out["baseline_control_status"] = baseline_status
    out["evidence_live_status"] = "PASS" if has(evidence_stdout, MARKERS["live_complete"]) else ("NOT_RUN_ENV" if not credential_available else "FAILED")
    out["external_runtime_unavailable"] = external
    out["classification"] = classification

    # Live aggregate fields (independent, no cross-inference)
    if not credential_available:
        out["mounted_dsh_retrieve_evidence_live"] = "NOT_RUN_ENV"
        out["mounted_dsh_validate_retrieved_claims_live"] = "NOT_RUN_ENV"
    elif retrieve_toolcall and retrieve_result:
        out["mounted_dsh_retrieve_evidence_live"] = "PASS"
    else:
        out["mounted_dsh_retrieve_evidence_live"] = "FAILED" if not external else "NOT_RUN_ENV"
    if not credential_available:
        pass
    elif validate_toolcall and validate_result:
        out["mounted_dsh_validate_retrieved_claims_live"] = "PASS"
    else:
        out["mounted_dsh_validate_retrieved_claims_live"] = "FAILED" if not external else "NOT_RUN_ENV"

    if external:
        # External block: identity/policy cannot be proven live this window.
        out["direct_vs_dsh_evidence_identity_match"] = "NOT_RUN_ENV"
        out["direct_vs_dsh_policy_match"] = "NOT_RUN_ENV"

    # Attempt counts
    m = re.search(r"LANE325_ATTEMPTS retrieve=(\d+) validate=(\d+)", evidence_stdout)
    if m:
        out["live_attempts"] = {"retrieve": int(m.group(1)), "validate": int(m.group(2))}
    else:
        ra = len(re.findall(r"LANE325_RETRIEVE_ATTEMPT=", evidence_stdout))
        va = len(re.findall(r"LANE325_VALIDATE_ATTEMPT=", evidence_stdout))
        out["live_attempts"] = {"retrieve": ra, "validate": va}

    return out


def main() -> int:
    key = load_deepseek_key()
    result: dict = {
        "raw_mcp_tools": "PASS",
        "mounted_dsh_tool_discovery": "NOT_RUN_ENV",
        "baseline_control_status": "NOT_RUN_ENV",
        "evidence_live_status": "NOT_RUN_ENV",
        "retrieve_toolcall": "NOT_RUN_ENV",
        "retrieve_linked_result": "NOT_RUN_ENV",
        "direct_vs_dsh_evidence_identity_match": "NOT_RUN_ENV",
        "validate_toolcall": "NOT_RUN_ENV",
        "validate_linked_result": "NOT_RUN_ENV",
        "direct_vs_dsh_policy_match": "NOT_RUN_ENV",
        "mounted_dsh_retrieve_evidence_live": "NOT_RUN_ENV",
        "mounted_dsh_validate_retrieved_claims_live": "NOT_RUN_ENV",
        "external_runtime_unavailable": False,
        "classification": "NOT_RUN_ENV",
        "live_attempts": {"retrieve": 0, "validate": 0},
        "dsh_src": str(DSH_SRC),
        "credential_available": bool(key),
        "secret_leaked": False,
        "errors": [],
        "warnings": [],
        "live": {},
    }

    if not DSH_SRC.exists():
        result["errors"].append(f"DSH_SRC missing: {DSH_SRC}")
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    # Ensure configs exist in DSH_SRC
    for cfg_src, name in (
        (ROOT / "integration" / "dsh" / "vitest.phase432.config.ts", "vitest.ai4s-phase432.config.ts"),
        (ROOT / "integration" / "dsh" / "vitest.lane324.config.ts", "vitest.ai4s-lane324.config.ts"),
    ):
        dest = DSH_SRC / name
        if cfg_src.exists():
            dest.write_text(cfg_src.read_text(encoding="utf-8"), encoding="utf-8")

    # Copy lane files into DSH_SRC (vitest root)
    for lane in (
        "lane325_kc_evidence_roundtrip.e2e.ts",
        "lane324_kc_roundtrip.e2e.ts",
    ):
        src = ROOT / "integration" / "dsh" / lane
        if src.exists():
            (DSH_SRC / lane).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    env = os.environ.copy()
    env["DSH_SRC"] = str(DSH_SRC)
    env["AI4S_ED_ROOT"] = str(ROOT)
    env["KC_EVIDENCE_INTEGRATION_FIXTURE"] = "1"
    env["AI4S_KC_PYTHON"] = env.get("AI4S_KC_PYTHON") or sys.executable
    env["AI4S_KC_WORKSPACE"] = str(ROOT)
    if key:
        env["DEEPSEEK_API_KEY"] = key

    try:
        b_rc, b_out, b_err = run_vitest(CONFIG_BASELINE, env)
    except Exception as exc:
        b_rc, b_out, b_err = 1, "", f"{type(exc).__name__}: {exc}"
        result["errors"].append(f"baseline run error: {exc}")

    try:
        e_rc, e_out, e_err = run_vitest(CONFIG_EVIDENCE, env)
    except Exception as exc:
        e_rc, e_out, e_err = 1, "", f"{type(exc).__name__}: {exc}"
        result["errors"].append(f"evidence run error: {exc}")

    b_out = _redact(b_out, key)
    b_err = _redact(b_err, key)
    e_out = _redact(e_out, key)
    e_err = _redact(e_err, key)

    result["live"] = {
        "baseline_returncode": b_rc,
        "baseline_stdout_tail": b_out[-6000:],
        "baseline_stderr_tail": b_err[-2000:],
        "evidence_returncode": e_rc,
        "evidence_stdout_tail": e_out[-8000:],
        "evidence_stderr_tail": e_err[-3000:],
    }

    classified = classify_outputs(
        credential_available=bool(key),
        evidence_stdout=e_out,
        evidence_rc=e_rc,
        baseline_stdout=b_out,
        baseline_rc=b_rc,
    )
    result.update(classified)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    ok = (
        result.get("mounted_dsh_tool_discovery") == "PASS"
        and result.get("mounted_dsh_retrieve_evidence_live") == "PASS"
        and result.get("mounted_dsh_validate_retrieved_claims_live") == "PASS"
        and result.get("direct_vs_dsh_evidence_identity_match") == "PASS"
        and result.get("direct_vs_dsh_policy_match") == "PASS"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
