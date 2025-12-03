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
from swecompass.evaluators.performance_optimization.parsers_time import get_parse_log
import requests
import xml.etree.ElementTree as ET
import time
import psutil
from typing import Dict, Any, Tuple

VERBOSE = False

def log(msg):
    if VERBOSE:
        print(msg)

# Execute system commands securely with error handling
def run_cmd(cmd: List[str],
            capture_output: bool = False,
            check: bool = True,
            env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
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

# Load docker image from tar file and extract tags
def docker_load_image(tar_path: Path) -> List[str]:
    if not tar_path.exists():
        raise FileNotFoundError(f"Docker tar not found: {tar_path}")
    proc = run_cmd(["docker", "load", "-i", str(tar_path)], capture_output=True, check=True)
    stdout = proc.stdout or ""
    log("[INFO] docker load output:\n" + stdout)
    tags = re.findall(r"Loaded image:\s+([^\s]+)", stdout)
    return tags

# Ensure container is running, creating it with resource limits if necessary
def ensure_container(image_tag: str, container_name: str, mount_dir: Path,
                     cpus_per_container: float = 5.0, mem_per_container_gb: float = 8.0) -> None:
    ps = run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, check=True)
    names = ps.stdout.splitlines() if ps.stdout else []

    if container_name in names:
        log(f"[INFO] Container '{container_name}' already exists. Starting if needed...")
        run_cmd(["docker", "start", container_name], check=False)
        return

    while True:
        total_cpus = psutil.cpu_count(logical=True)
        total_mem_gb = psutil.virtual_memory().total / (1024**3)

        cpu_usage = psutil.cpu_percent(interval=1)
        mem_info = psutil.virtual_memory()
        mem_usage = mem_info.percent

        log(f"[INFO] CPU usage={cpu_usage:.1f}%, Mem usage={mem_usage:.1f}%")

        if cpu_usage < 80 and mem_usage < 80:
            log(f"[INFO] Creating container '{container_name}' ({cpus_per_container} CPUs, {mem_per_container_gb}GB RAM)")
            run_cmd([
                "docker", "run", "-dit",
                "--network=host", "--privileged",
                "--name", container_name,
                f"--cpus={cpus_per_container}",
                f"--memory={mem_per_container_gb}g",
                image_tag, "bash"
            ], check=True)
            break
        else:
            log("[WARN] System busy (CPU>80% or Mem>80%), waiting 30s...")
            time.sleep(30)

# Copy file from host to container
def docker_cp_to_container(container_name: str, src: Path, dst_in_container: str) -> None:
    dst_dir = os.path.dirname(dst_in_container)
    subprocess.run(["docker", "exec", container_name, "mkdir", "-p", dst_dir], check=True)
    cmd = ["docker", "cp", str(src), f"{container_name}:{dst_in_container}"]
    subprocess.run(cmd, check=True)

# Execute bash script inside container and log output
def docker_exec_bash(container_name: str, bash_script: str, logfile: Optional[Path] = None, timeout: int = 4000) -> int:
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

# Load patch content from file or default text
def load_patch_text(patch_file_cli: Optional[Path], patch_default: str) -> str:
    if patch_file_cli:
        return Path(patch_file_cli).read_text(encoding="utf-8")
    return patch_default

# Write content to file, creating parent directories if needed
def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# Evaluate performance improvement coverage for PASS and FAIL sets
def check_pass_coverage(t1: str | Path,
                        t2: str | Path,
                        pass_file: str | Path,
                        fail_file: str | Path,
                        threshold: float = 0.5) -> Tuple[bool, bool]:
    def load_json(path):
        if not path or not Path(path).exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    accelerate_rate = 0.8
    t1 = load_json(t1)
    t2 = load_json(t2)
    try:
        with open(pass_file, "r", encoding="utf-8") as f:
            pass_to_pass = set(json.load(f))
    except Exception:
        pass_to_pass = set()

    try:
        with open(fail_file, "r", encoding="utf-8") as f:
            fail_to_pass = set(json.load(f))
    except Exception:
        fail_to_pass = set()

    pass_ok = True
    for test_name in pass_to_pass:
        if test_name not in t2:
            pass_ok = False
            break
        t2_time = t2[test_name]
        if not isinstance(t2_time, (int, float)) or t2_time <= 0:
            pass_ok = False
            break

    improved_keys = set()
    for test_name, t1_time in t1.items():
        if test_name not in t2:
            continue
        t2_time = t2[test_name]
        if not isinstance(t1_time, (int, float)) or not isinstance(t2_time, (int, float)):
            continue
        if t1_time <= 0 or t2_time <= 0:
            continue
        if t1_time * accelerate_rate > t2_time:
            improved_keys.add(test_name)

    if fail_to_pass:
        overlap = improved_keys & fail_to_pass
        coverage_ratio = len(overlap) / len(fail_to_pass)
        fail_ok = coverage_ratio >= threshold
    else:
        fail_ok = True

    return pass_ok, fail_ok


# Run a test stage: apply patches, execute tests, and parse logs
def run_stage(container: str, stage_branch: str, base_commit: str,
              pre_cmd: str, test_cmd: str, proxy_env: Dict[str, str],
              apply_tests: bool, apply_code: bool,
              logfile: Path,
              rec_logfile: Path,
              parsed_file: Path,repo_key: str) -> int:

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

    test_script = "\n".join([
        *proxy_exports,
        test_cmd
    ])
    rc = docker_exec_bash(container, test_script, logfile=logfile)
    try:
        parser = get_parse_log(repo_key)
        if parser is None:
            log("Parser Not Found")
            return 999
        parsed = parser(logfile)
        parsed_file.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"[WARN] Failed to parse log {logfile}: {e}")

    return rc

# Extract repository name from URL
def infer_repo_name(repo_url: str) -> str:
    tail = repo_url.rstrip("/").split("/")[-1]
    return tail[:-4] if tail.endswith(".git") else tail

# Define output file paths
def build_output_paths(root: Path) -> Dict[str, Path]:
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
    if file_arg:
        with open(file_arg, "r", encoding="utf-8") as f:
            return f.read()
    if text_arg:
        return codecs.decode(text_arg, "unicode_escape")
    return codecs.decode(default_text, "unicode_escape")

# Main execution logic
def main(args: argparse.Namespace) -> None:
    repo_name = args.repo_name or infer_repo_name(args.repo_url)
    if not args.pr_number:
        raise SystemExit("--pr-number 为必填参数（用于产物目录划分）")
    out_root = Path(args.work_root)
    out_root.mkdir(parents=True, exist_ok=True)
    paths = build_output_paths(out_root)

    image_tag = args.image_tag

    ensure_container(image_tag, args.container_name, out_root)

    test_patch_text = load_patch(args.tests_patch, args.tests_patch_file, default_text="TEST_PATCH_DEFAULT")
    code_patch_text = load_patch(args.code_patch, args.code_patch_file, default_text="CODE_PATCH_DEFAULT")
    pre_test_cmd = Path(args.test_cmd_file).read_text(encoding="utf-8")
    test_cmd = args.test_cmd

    write_text(paths["patch_tests"], test_patch_text)
    write_text(paths["patch_code"], code_patch_text)

    docker_cp_to_container(args.container_name, paths["patch_tests"], "/patches/pr_tests.patch")
    docker_cp_to_container(args.container_name, paths["patch_code"], "/patches/pr_code.patch")

    proxy_env = {
        "http_proxy": args.http_proxy or "",
        "https_proxy": args.https_proxy or "",
        "HTTP_PROXY": args.http_proxy or "",
        "HTTPS_PROXY": args.https_proxy or "",
        "no_proxy": args.no_proxy or "",
        "NO_PROXY": args.no_proxy or "",
    }
    rc_d = run_stage(
        args.container_name, "stage_d", args.base_commit, pre_test_cmd,test_cmd, proxy_env,
        apply_tests=True, apply_code=False, logfile=paths["run_test"],rec_logfile=paths["log_test"], parsed_file=paths["parsed_test"],repo_key=args.repo_name
    )
    rc_e = run_stage(
        args.container_name, "stage_e", args.base_commit, pre_test_cmd,test_cmd, proxy_env,
        apply_tests=True, apply_code=True, logfile=paths["run_test_patch"],rec_logfile=paths["log_test_patch"], parsed_file=paths["parsed_test_patch"],repo_key=args.repo_name
    )
    log(f"[INFO] stage_e exit code: {rc_e}")

    PASS_TO_PASS, FAIL_TO_PASS = False,False
    if paths["parsed_test_patch"].exists():
        PASS_TO_PASS, FAIL_TO_PASS = check_pass_coverage(paths["parsed_test"],paths["parsed_test_patch"],args.pass_to_pass_file,args.fail_to_pass_file)

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
    result = {
        "repo": repo_name,
        "pr_number": str(args.pr_number),
        "base_commit": args.base_commit,
        "run_state": run_state,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "PASS_TO_PASS_result": PASS_TO_PASS,
        "FAIL_TO_PASS_result": FAIL_TO_PASS,
    }
    write_text(paths["result_json"], json.dumps(result, ensure_ascii=False, indent=2))
    log(f"[INFO] All done. Artifacts saved under: {str(out_root)}")
    try:
        log(f"[INFO] Stopping and removing container: {args.container_name}")
        run_cmd(["docker", "stop", args.container_name], check=False)
        run_cmd(["docker", "rm", "-f", args.container_name], check=False)
    except Exception as e:
        log(f"[WARN] Failed to remove container {args.container_name}: {e}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Commit-Pack Runner (docker load + 4-stage test + LLM judge)")

    parser.add_argument("--base-commit", default="", help="Base commit hash")
    parser.add_argument("--test-cmd", default="", help="Test command")
    parser.add_argument("--repo_name", default="", help="Repository name")
    parser.add_argument("--test-cmd-file", default=None, help="Test command (file path)")

    parser.add_argument("--pr-number", default=12907, help="PR number (used for artifact directory)")
    parser.add_argument("--work-root", default="", help="Root directory for artifacts")

    parser.add_argument("--container-name", default="astropy-12907", help="Container name")
    parser.add_argument("--image-tag", default="swebench/sweb.eval.x86_64.astropy_1776_astropy-12907", help="Image name:tag (parsed from docker load output if not provided)")

    parser.add_argument("--http-proxy", default="", help="http_proxy/HTTP_PROXY")
    parser.add_argument("--https-proxy", default="", help="https_proxy/HTTPS_PROXY")
    parser.add_argument("--no-proxy", default="", help="no_proxy/NO_PROXY")

    parser.add_argument("--tests-patch", default=None, help="External tests patch content")
    parser.add_argument("--code-patch", default=None, help="External code patch content")
    parser.add_argument("--tests-patch-file", default=None, help="External tests patch file path")
    parser.add_argument("--code-patch-file", default=None, help="External code patch file path")

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