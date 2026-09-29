"""Phase 3.2 DSH package qualification via real source-built 0.2 Loader.

Uses the pinned external checkout; set DSH_SRC to its absolute path.
Does not run a live LLM turn.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

DSH_SRC = Path(os.environ.get("DSH_SRC", ""))
if not str(DSH_SRC):
    raise SystemExit("DSH_SRC environment variable is required")
PRODUCT_BUNDLE = Path("dsh/knowledge-curator")
QUALIF_PATCH = Path("integration/dsh/fixtures/knowledge-curator-qualification.patch.yml")
RESULT_PATH = Path("results/phase-03-2-dsh-package-qualification.json")

EXPECTED_TOOL = "mcp__knowledge_curator__curate_assertion_set"


def run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
    # On Windows pnpm may be a shell shim; use cmd /c for robustness.
    if sys.platform == "win32" and cmd and cmd[0] in ("pnpm", "pnpm.cmd"):
        cmd = ["cmd", "/c"] + cmd
    elif sys.platform == "win32" and cmd and cmd[0] == "node":
        pass
    env = {**os.environ}
    home = Path(os.environ.get("TEMP", "/tmp")) / "dsh-qual-home"
    home.mkdir(parents=True, exist_ok=True)
    env["DSH_HOME"] = os.environ.get("DSH_HOME", str(home))
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def qualify() -> dict:
    result: dict = {
        "upstream_repo": "https://github.com/deepseek-ai/deepseek-harness",
        "upstream_commit": "4878cdabd87d4041bdaff61d04c966883b9fd07a",
        "dsh_version": "",
        "node_version": "",
        "pnpm_version": "",
        "source_build_passed": False,
        "loader_config_passed": False,
        "preset_declared": False,
        "preset_broken": True,
        "preset_mount_tested": False,
        "preset_mount_passed": False,
        "product_bundle_contains_registry": False,
        "expected_public_mcp_tool": EXPECTED_TOOL,
        "errors": [],
        "warnings": [],
    }

    # Versions
    code, out, _ = run(["node", "--version"], DSH_SRC)
    result["node_version"] = out.strip() if code == 0 else "unknown"
    code, out, _ = run(["pnpm", "--version"], DSH_SRC)
    result["pnpm_version"] = out.strip() if code == 0 else "unknown"

    # Source commit / version
    code, out, _ = run(["git", "rev-parse", "HEAD"], DSH_SRC)
    commit = out.strip()
    if commit != result["upstream_commit"]:
        result["errors"].append(f"commit mismatch: {commit}")
    code, out, err = run(["pnpm", "dsh", "--version"], DSH_SRC)
    version = out.strip().splitlines()[-1] if out.strip() else err.strip()
    result["dsh_version"] = version
    if "0.2.0-rc.1" in version:
        result["source_build_passed"] = True
    else:
        result["errors"].append(f"dsh version unexpected: {version!r}")

    # Product bundle must not contain registry (ignore comments)
    patch_text = (PRODUCT_BUNDLE / "cordis.patch.yml").read_text(encoding="utf-8")
    active_lines = "\n".join(
        line for line in patch_text.splitlines() if not line.strip().startswith("#")
    )
    result["product_bundle_contains_registry"] = "agent-preset-registry" in active_lines

    # Real Loader: dump-config with product bundle patch
    bundle_patch = str((PRODUCT_BUNDLE / "cordis.patch.yml").resolve())
    code, out, err = run(
        ["pnpm", "dsh", "--profile", "sdk-minimal", "--patch", bundle_patch, "--dump-config"],
        DSH_SRC,
        timeout=60,
    )
    loader_ok = code == 0 and "knowledge-curator" in out
    if loader_ok:
        result["loader_config_passed"] = True
        result["preset_declared"] = "preset-knowledge-curator" in out or "knowledge-curator" in out
        result["preset_broken"] = "broken" in out.lower() and "knowledge-curator" in out
    else:
        result["errors"].append(f"loader dump-config failed code={code}: {err[-400:]}")

    # Child plugins resolve names
    for pkg in ("@deepseek-ai/dsh-persona", "@deepseek-ai/dsh-mcp-client", "@deepseek-ai/dsh-agent-preset"):
        if pkg in out:
            pass
        else:
            result["warnings"].append(f"{pkg} not visible in dump-config output")

    # Qualification fixture: registry + product preset
    qualif = str(QUALIF_PATCH.resolve())
    code, out2, err2 = run(
        ["pnpm", "dsh", "--profile", "sdk-minimal", "--patch", qualif, "--dump-config"],
        DSH_SRC,
        timeout=60,
    )
    if code == 0:
        if "agent-preset-registry" in out2 and "knowledge-curator" in out2:
            result["preset_declared"] = True
            result["preset_broken"] = "broken: knowledge-curator" in out2 or "preset-knowledge-curator\n  broken" in out2
        # persona / mcp client rows
        if "dsh-persona" in out2:
            result["warnings"].append("persona row present in qualification config")
        if "dsh-mcp-client" in out2:
            result["warnings"].append("mcp-client row present in qualification config")
    else:
        result["errors"].append(f"qualification loader failed: {err2[-300:]}")

    # mount is Phase 3.2 optional
    result["preset_mount_tested"] = False
    result["preset_mount_passed"] = False

    return result


if __name__ == "__main__":
    r = qualify()
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    sys.exit(0 if r["source_build_passed"] and r["loader_config_passed"] else 1)
