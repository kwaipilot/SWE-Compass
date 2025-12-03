#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
import codecs
from typing import List, Optional, Tuple, Dict
from swecompass.evaluators.selected.parsers import get_parse_log
import requests
import xml.etree.ElementTree as ET

VERBOSE = False

def log(msg):
    if VERBOSE:
        print(msg)

# =========================
# Subprocess Execution Helper
# =========================
def run_cmd(cmd: List[str],
            capture_output: bool = False,
            check: bool = True,
            env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    # Execute system command safely
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    log(f"[RUN] {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        check=check,
        env=env
    )


# =========================
# Docker Operations
# =========================
def docker_load_image(tar_path: Path) -> List[str]:
    # Load docker image from tar and extract tags
    if not tar_path.exists():
        raise FileNotFoundError(f"Docker tar not found: {tar_path}")
    proc = run_cmd(["docker", "load", "-i", str(tar_path)], capture_output=True, check=True)
    stdout = proc.stdout or ""
    log("[INFO] docker load output:\n" + stdout)
    tags = re.findall(r"Loaded image:\s+([^\s]+)", stdout)
    return tags


def ensure_container(image_tag: str, container_name: str, mount_dir: Path) -> None:
    # Ensure container exists and is running
    ps = run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, check=True)
    names = ps.stdout.splitlines() if ps.stdout else []
    if container_name in names:
        log(f"[INFO] Container '{container_name}' already exists. Starting if needed...")
        run_cmd(["docker", "start", container_name], check=False)
    else:
        log(f"[INFO] Creating container '{container_name}' from image '{image_tag}'")
        run_cmd([
            "docker", "run", "-dit","--network=host","--privileged",
            "--name", container_name,
            image_tag, "bash"
        ], check=True)

def docker_cp_to_container(container_name: str, src: Path, dst_in_container: str) -> None:
    # Copy file from host to container
    dst_dir = os.path.dirname(dst_in_container)
    subprocess.run(["docker", "exec", container_name, "mkdir", "-p", dst_dir], check=True)
    cmd = ["docker", "cp", str(src), f"{container_name}:{dst_in_container}"]
    subprocess.run(cmd, check=True)

def docker_exec_bash(container_name: str, bash_script: str, logfile: Optional[Path] = None, timeout: int = 4000) -> int:
    # Execute bash script inside container
    cmd = ["docker", "exec", container_name, "bash", "-lc", bash_script]
    log(f"[EXEC in {container_name}] bash -lc <<SCRIPT\n{bash_script}\nSCRIPT")

    try:
        if logfile:
            logfile.parent.mkdir(parents=True, exist_ok=True)
            with open(logfile, "a", encoding="utf-8") as f:
                f.write(f"\n\n[EXEC in {container_name}] >>> {bash_script}\n")
                f.write("=" * 80 + "\n")
                f.flush()
                proc = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=timeout
                )
            return proc.returncode
        else:
            proc = subprocess.run(cmd, timeout=timeout)
            return proc.returncode
    except subprocess.TimeoutExpired:
        log(f"[WARN] Command timeout after {timeout} seconds in container {container_name}")
        if logfile:
            with open(logfile, "a", encoding="utf-8") as f:
                f.write(f"\n[ERROR] Command timed out after {timeout} seconds\n")
        return 124

# =========================
# Patch and File I/O
# =========================
def load_patch_text(patch_file_cli: Optional[Path], patch_default: str) -> str:
    # Load patch text from file or default
    if patch_file_cli:
        return Path(patch_file_cli).read_text(encoding="utf-8")
    return patch_default


def write_text(path: Path, content: str) -> None:
    # Write content to file with UTF-8 encoding
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# =========================
# Validation Logic
# =========================
def check_pass_coverage(parsed_file: str,
                        pass_file: str,
                        fail_file: str) -> Tuple[bool, bool]:
    # Check if PASSED/FAILED tests cover the requirements
    
    with open(parsed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    passed_keys = {k for k, v in data.items() if v == "PASSED"}
    failed_keys = {k for k, v in data.items() if v == "FAILED"}

    try:
        with open(pass_file, "r", encoding="utf-8") as f:
            pass_to_pass = json.load(f)
    except Exception:
        pass_to_pass = []

    try:
        with open(fail_file, "r", encoding="utf-8") as f:
            fail_to_pass = json.load(f)
    except Exception:
        fail_to_pass = []
    
    # PASS_TO_PASS keys must not be in the failed set
    covers_pass = all(item not in failed_keys for item in pass_to_pass)
    # FAIL_TO_PASS keys must be in the passed set
    covers_fail = all(item in passed_keys for item in fail_to_pass)

    return covers_pass, covers_fail


def run_stage(container: str, stage_branch: str, base_commit: str,
              pre_cmd: str, test_cmd: str, proxy_env: Dict[str, str],
              apply_tests: bool, apply_code: bool,
              logfile: Path,
              rec_logfile: Path,
              parsed_file: Path,repo_key: str) -> int:
    # Execute a test stage (checkout, apply patches, run test, parse log)

    # Proxy settings
    proxy_exports = []
    for k, v in proxy_env.items():
        if v:
            proxy_exports.append(f"export {k}={shlex.quote(v)}")

    pre_cmds = [
        *proxy_exports,
        "cd /testbed",
        f"git reset --hard {base_commit}",
        f"git checkout -B {stage_branch}",
    ]
    need_clean = ["arrow","loki","matrixone","bitcoin-old","scipy","mypy","keras","renovate","docs"]
    if repo_key not in need_clean:
        pre_cmds = [
            *proxy_exports,
            "cd /testbed",
            f"git clean -fdx; git reset --hard {base_commit}; git clean -fdx; git reset --hard {base_commit}",
            f"git checkout -B {stage_branch}",
        ]
    if apply_tests:
        pre_cmds.append("git apply -v --reject --whitespace=fix /patches/pr_tests.patch")
    if apply_code:
        pre_cmds.append("git apply -v --reject --whitespace=fix /patches/pr_code.patch")
    pre_cmds.append(pre_cmd)
    pre_script = "\n".join(pre_cmds)
    docker_exec_bash(container, pre_script, logfile=rec_logfile)

    # Run tests
    test_script = "\n".join([
        *proxy_exports,
        test_cmd
    ])
    rc = docker_exec_bash(container, test_script, logfile=logfile)
    
    # Parse log and save JSON
    try:
        parser = get_parse_log(repo_key)
        if parser is None:
            log("Parser Not Found")
            return 999
        parsed = parser(logfile.read_text(encoding="utf-8", errors="ignore"))
        parsed_file.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"[WARN] Failed to parse log {logfile}: {e}")

    return rc


# =========================
# Main Workflow
# =========================
def infer_repo_name(repo_url: str) -> str:
    # Infer repository name from URL
    tail = repo_url.rstrip("/").split("/")[-1]
    return tail[:-4] if tail.endswith(".git") else tail


def build_output_paths(root: Path) -> Dict[str, Path]:
    # Define output paths for artifacts
    return {
        "patch_tests": root / "pr_tests.patch", 
        "patch_code": root / "pr_code.patch", 
        "run_initial": root / "run_initial.log",
        "run_test": root / "run_test.log",
        "run_test_patch": root / "run_test_patch.log",
        "log_initial": root / "log_initial.log",
        "log_test": root / "log_test.log",
        "log_test_patch": root / "log_test_patch.log",
        "parsed_initial": root / "parsed_initial.json",
        "parsed_test": root / "parsed_test.json",
        "parsed_test_patch": root / "parsed_test_patch.json",
        "diff": root / "diff_F2P.txt",
        "result_json": root / "result.json",
    }

def load_patch(text_arg, file_arg, default_text=""):
    if file_arg:  # Read from file
        with open(file_arg, "r", encoding="utf-8") as f:
            return f.read()
    if text_arg:  # Read from CLI string
        return codecs.decode(text_arg, "unicode_escape")
    return codecs.decode(default_text, "unicode_escape")

def main(args: argparse.Namespace) -> None:
    # 1) Setup output paths
    repo_name = args.repo_name or infer_repo_name(args.repo_url)
    if not args.pr_number:
        raise SystemExit("--pr-number is required")
    out_root = Path(args.work_root)
    out_root.mkdir(parents=True, exist_ok=True)
    paths = build_output_paths(out_root)

    # 2) Load image
    image_tag = args.image_tag

    # 3) Ensure container
    ensure_container(image_tag, args.container_name, out_root)

    # 4) Prepare patches
    test_patch_text = load_patch(args.tests_patch, args.tests_patch_file, default_text="TEST_PATCH_DEFAULT")
    code_patch_text = load_patch(args.code_patch, args.code_patch_file, default_text="CODE_PATCH_DEFAULT")
    pre_test_cmd = Path(args.test_cmd_file).read_text(encoding="utf-8")
    test_cmd = args.test_cmd

    write_text(paths["patch_tests"], test_patch_text)
    write_text(paths["patch_code"], code_patch_text)

    docker_cp_to_container(args.container_name, paths["patch_tests"], "/patches/pr_tests.patch")
    docker_cp_to_container(args.container_name, paths["patch_code"], "/patches/pr_code.patch")

    # 5) Run stage E (base + test + code)
    proxy_env = {
        "http_proxy": args.http_proxy or "",
        "https_proxy": args.https_proxy or "",
        "HTTP_PROXY": args.http_proxy or "",
        "HTTPS_PROXY": args.https_proxy or "",
        "no_proxy": args.no_proxy or "",
        "NO_PROXY": args.no_proxy or "",
    }

    rc_e = run_stage(
        args.container_name, "stage_e", args.base_commit, pre_test_cmd,test_cmd, proxy_env,
        apply_tests=True, apply_code=True, logfile=paths["run_test_patch"],rec_logfile=paths["log_test_patch"], parsed_file=paths["parsed_test_patch"],repo_key=args.repo_name
    )
    log(f"[INFO] stage_e exit code: {rc_e}")

    PASS_TO_PASS, FAIL_TO_PASS = False,False
    if paths["parsed_test_patch"].exists():
        PASS_TO_PASS, FAIL_TO_PASS = check_pass_coverage(paths["parsed_test_patch"],args.pass_to_pass_file,args.fail_to_pass_file)

    run_state = True
    if not paths["parsed_test_patch"].exists() or paths["parsed_test_patch"].stat().st_size == 0:
        run_state = False
    try:
        data = json.loads(paths["parsed_test_patch"].read_text(encoding="utf-8"))
        if not data:
            run_state = False
    except Exception:
            run_state = False

    try:
        with open(args.pass_to_pass_file, "r", encoding="utf-8") as f:
            pass_to_pass_list = json.load(f)
    except Exception:
        pass_to_pass_list = []

    try:
        with open(args.fail_to_pass_file, "r", encoding="utf-8") as f:
            fail_to_pass_list = json.load(f)
    except Exception:
        fail_to_pass_list = []
    write_text(out_root / "PASS_TO_PASS_list.json", json.dumps(pass_to_pass_list, ensure_ascii=False, indent=2))
    write_text(out_root / "FAIL_TO_PASS_list.json", json.dumps(fail_to_pass_list, ensure_ascii=False, indent=2))
    
    # 9) Write result.json
    result = {
        "repo": repo_name,
        "pr_number": str(args.pr_number),
        "base_commit": args.base_commit,
        "run_state": run_state,
        "PASS_TO_PASS_result": PASS_TO_PASS,
        "FAIL_TO_PASS_result": FAIL_TO_PASS,
    }
    write_text(paths["result_json"], json.dumps(result, ensure_ascii=False, indent=2))
    log(f"[INFO] All done. Artifacts saved under: {str(out_root)}")
    
    # 10) Cleanup container
    try:
        log(f"[INFO] Stopping and removing container: {args.container_name}")
        run_cmd(["docker", "stop", args.container_name], check=False)
        run_cmd(["docker", "rm", "-f", args.container_name], check=False)
    except Exception as e:
        log(f"[WARN] Failed to remove container {args.container_name}: {e}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Commit-Pack Runner (docker load + 4-stage test + LLM judge)")

    # Basic source info
    parser.add_argument("--base-commit", default="", help="Base commit hash")
    parser.add_argument("--test-cmd", default="", help="Test command")
    parser.add_argument("--repo_name", default="", help="Repository name")
    parser.add_argument("--test-cmd-file", default=None, help="File containing test command")

    # Artifact paths
    parser.add_argument("--pr-number", default=12907, help="PR number (used for artifact directory)")
    parser.add_argument("--work-root", default="", help="Root directory for artifacts")

    # Docker execution
    parser.add_argument("--container-name", default="astropy-12907", help="Container name")
    parser.add_argument("--image-tag", default="swebench/sweb.eval.x86_64.astropy_1776_astropy-12907", help="Image tag (if not provided, parsed from docker load output)")

    # Proxy settings
    parser.add_argument("--http-proxy", default="", help="http_proxy/HTTP_PROXY")
    parser.add_argument("--https-proxy", default="", help="https_proxy/HTTPS_PROXY")
    parser.add_argument("--no-proxy", default="", help="no_proxy/NO_PROXY")

    # Patch sources
    parser.add_argument("--tests-patch", default=None, help="External test patch content")
    parser.add_argument("--code-patch", default=None, help="External code patch content")
    parser.add_argument("--tests-patch-file", default=None, help="External test patch file path")
    parser.add_argument("--code-patch-file", default=None, help="External code patch file path")

    # Validation set
    parser.add_argument("--pass-to-pass-file", type=str, required=True, help="JSON file containing PASS_TO_PASS list")
    parser.add_argument("--fail-to-pass-file", type=str, required=True, help="JSON file containing FAIL_TO_PASS list")


    args = parser.parse_args()
    try:
        main(args)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {e}", file=sys.stderr)
        sys.exit(e.returncode)
    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        sys.exit(1)