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
import xml.etree.ElementTree as ET

import requests

VERBOSE = True

def log(msg):
    if VERBOSE:
        print(msg)

# Parse test logs based on repository-specific patterns to determine pass/fail status
def parse_log(log: str, repo_name) -> dict[str, str]:
    repo = repo_name
    status_map = {}
    if repo == 'runelite':
        pattern = re.compile(r"\[INFO\]\s+(\w+)\s+\.+\s+\w+\s+\[", re.IGNORECASE) 
        for line in log.splitlines():
            m = pattern.search(line)
            if not m:
                continue
            name = m.group(1)
            if 'SUCCESS' in line:
                status = "PASSED"
            elif 'FAILURE' in line:
                status = 'FAILED'
            elif 'SKIPPED' in line:
                status = "SKIPPED"
            else:
                status = "UNKNOWN"
            status_map[name] = status
    elif repo == 'kiota':
        pattern = re.compile(r".*?(Kiota\.[\w.]+)\s+.*?", re.IGNORECASE)
        for line in log.splitlines():
            m = pattern.search(line)
            if not m:
                continue
            name = m.group(1)
            if "Passed" in line:
                status = "PASSED"
            elif "Failed" in line:
                status = "FAILED"
            elif "Error" in line:
                status = "ERROR"
            elif "Skipped" in line:
                status = "SKIPPED"
            elif "XFAIL" in line:
                status = "XFAIL"
            else:
                status = "UNKNOWN"
            status_map[name] = status
    elif repo == 'systemd':
        pattern = re.compile(r"^\s*\d+/\d+\s+systemd:\s*(.+?)\s+(OK|FAIL|SKIP|TIMEOUT)\b", re.IGNORECASE)

        for line in log.splitlines():
            line = line.strip()
            m = pattern.match(line)
            if not m:
                continue
            name = m.group(1).strip()
            result = m.group(2).upper()

            if result == "OK":
                status = "PASSED"
            elif result == "FAIL" or result == "TIMEOUT":
                status = "FAILED"
            elif result == "SKIP":
                status = "SKIPPED"
            else:
                status = "UNKNOWN"

            status_map[name] = status
    elif repo == 'godot':
        m = re.search(r"(<testsuites[\s\S]*</testsuites>)", log)
        if not m:
            return {}
        xml_str = m.group(1)

        root = ET.fromstring(xml_str)
        status_map = {}
        for tc in root.iter("testcase"):
            name = f"{tc.get('classname')}::{tc.get('name')}"
            if tc.find("skipped") is not None:
                status = "SKIPPED"
            elif tc.find("failure") is not None or tc.find("error") is not None:
                status = "FAILED"
            else:
                status = "PASSED"
            status_map[name] = status
    elif repo == 'eslint':
        seen_failure_numbers = set()

        for line in log.splitlines():
            line = line.strip()

            if line.startswith('✓'):
                test_name = line[1:].strip()
                test_name = re.sub(r'\s*\(\d+ms\)\s*$', '', test_name)
                status_map[test_name] = "PASSED"

            elif re.match(r'^\d+\)', line):
                match = re.match(r'^(\d+)\)\s*(.+)', line)
                if match:
                    failure_number = match.group(1)
                    test_name = match.group(2).strip()

                    if failure_number not in seen_failure_numbers:
                        seen_failure_numbers.add(failure_number)
                        status_map[test_name] = "FAILED"
    elif repo == 'svelte':
        for line in log.splitlines():
            line = line.strip()

            if line.startswith('✓'):
                parts = line.split(' ', 1)
                if len(parts) > 1:
                    test_path = parts[1]
                    status_map[test_path] = "PASSED"

            elif line.startswith('FAIL'):
                parts = line.split(' ', 1)
                if len(parts) > 1:
                    test_path = parts[1].split('[')[0].strip()
                    status_map[test_path] = "FAILED"
    elif repo == 'dgs-framework':
        lines = log.split('\n')
        test_section_started = False
        test_lines = []

        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if re.match(r'^[\w.$]+\s+(PASSED|FAILED|ERROR|SKIPPED|NO_TESTS)$', line):
                test_lines.insert(0, line)
                test_section_started = True
            elif test_section_started and line and not re.match(r'^[\w.$]+\s+(PASSED|FAILED|ERROR|SKIPPED|NO_TESTS)$', line):
                break

        pattern = re.compile(r'^([\w.$]+)\s+(PASSED|FAILED|ERROR|SKIPPED|NO_TESTS)$')

        for line in test_lines:
            match = pattern.match(line.strip())
            if match:
                test_name = match.group(1)
                status = match.group(2)
                if '.' in test_name or (test_name and test_name[0].isupper()):
                    status_map[test_name] = status
    elif repo == 'graphql-kotlin':
        lines = log.split('\n')
        test_section_started = False
        test_lines = []

        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if re.match(r'^[\w.$]+\s+(PASSED|FAILED|ERROR|SKIPPED|NO_TESTS)$', line):
                test_lines.insert(0, line)
                test_section_started = True
            elif test_section_started and line and not re.match(r'^[\w.$]+\s+(PASSED|FAILED|ERROR|SKIPPED|NO_TESTS)$', line):
                break

        pattern = re.compile(r'^([\w.$]+)\s+(PASSED|FAILED|ERROR|SKIPPED|NO_TESTS)$')

        for line in test_lines:
            match = pattern.match(line.strip())
            if match:
                test_name = match.group(1)
                status = match.group(2)
                if '.' in test_name or (test_name and test_name[0].isupper()):
                    status_map[test_name] = status
    elif repo == 'rust-analyzer':
        pattern = re.compile(r"^test\s+(.+?)\s+\.\.\.\s+(ok|FAILED|ignored|ERROR)", re.MULTILINE)

        for match in pattern.finditer(log):
            test_name = match.group(1).strip()
            status = match.group(2)

            if status == "ok":
                status_map[test_name] = "PASSED"
            elif status == "FAILED":
                status_map[test_name] = "FAILED"
            elif status == "ignored":
                status_map[test_name] = "SKIPPED"
            elif status == "ERROR":
                status_map[test_name] = "ERROR"
            else:
                status_map[test_name] = "UNKNOWN"
    elif repo == 'rust-clippy':
        pattern = re.compile(r"^test\s+(.+?)\s+\.\.\.\s+(ok|FAILED|ignored|ERROR)", re.MULTILINE)

        for match in pattern.finditer(log):
            test_name = match.group(1).strip()
            status = match.group(2)

            if status == "ok":
                status_map[test_name] = "PASSED"
            elif status == "FAILED":
                status_map[test_name] = "FAILED"
            elif status == "ignored":
                status_map[test_name] = "SKIPPED"
            elif status == "ERROR":
                status_map[test_name] = "ERROR"
            else:
                status_map[test_name] = "UNKNOWN"
        
        status_map[name] = status
    return status_map

# Execute shell commands securely
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

# Load docker image from tar file and retrieve tags
def docker_load_image(tar_path: Path) -> List[str]:
    if not tar_path.exists():
        raise FileNotFoundError(f"Docker tar not found: {tar_path}")
    proc = run_cmd(["docker", "load", "-i", str(tar_path)], capture_output=True, check=True)
    stdout = proc.stdout or ""
    log("[INFO] docker load output:\n" + stdout)
    tags = re.findall(r"Loaded image:\s+([^\s]+)", stdout)
    return tags

# Ensure container is running, create if necessary
def ensure_container(image_tag: str, container_name: str, mount_dir: Path) -> None:
    ps = run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, check=True)
    names = ps.stdout.splitlines() if ps.stdout else []
    if container_name in names:
        log(f"[INFO] Container '{container_name}' already exists. Starting if needed...")
        run_cmd(["docker", "start", container_name], check=False)
    else:
        log(f"[INFO] Creating container '{container_name}' from image '{image_tag}'")
        run_cmd([
            "docker", "run", "-dit","--network=host",
            "--name", container_name,
            image_tag, "bash"
        ], check=True)

# Copy files from host to container
def docker_cp_to_container(container_name: str, src: Path, dst_in_container: str) -> None:
    dst_dir = os.path.dirname(dst_in_container)
    subprocess.run(["docker", "exec", container_name, "mkdir", "-p", dst_dir], check=True)
    cmd = ["docker", "cp", str(src), f"{container_name}:{dst_in_container}"]
    subprocess.run(cmd, check=True)

# Execute bash script inside container
def docker_exec_bash(container_name: str, bash_script: str, logfile: Optional[Path] = None, timeout: int = 6000) -> int:
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

# Helper: Load patch content
def load_patch_text(patch_file_cli: Optional[Path], patch_default: str) -> str:
    if patch_file_cli:
        return Path(patch_file_cli).read_text(encoding="utf-8")
    return patch_default

# Helper: Write content to file
def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# Execute a test stage: setup git, apply patches, run test, and parse logs
def run_stage(container: str, stage_branch: str, base_commit: str,
              pre_cmd: str, test_cmd: str, proxy_env: Dict[str, str],
              apply_tests: bool, apply_code: bool,
              logfile: Path,
              rec_logfile: Path,
              parsed_file: Path, repo_name) -> int:

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
    pre_cmds.append("git apply -v --reject --whitespace=fix /patches/cd_patch_path.patch")
    pre_cmds.append(pre_cmd)
    pre_script = "\n".join(pre_cmds)
    docker_exec_bash(container, pre_script, logfile=rec_logfile)

    test_script = "\n".join([
        *proxy_exports,
        test_cmd
    ])
    rc = docker_exec_bash(container, test_script, logfile=logfile)

    parsed = parse_log(logfile.read_text(encoding="utf-8", errors="ignore"), repo_name)
    parsed_file.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

    return rc

# Verify if pass/fail lists are covered by current results
def check_pass_coverage(parsed_file: str,
                        pass_file: str,
                        fail_file: str) -> Tuple[bool, bool]:

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
    
    covers_pass = all(item not in failed_keys for item in pass_to_pass)
    covers_fail = all(item in passed_keys for item in fail_to_pass)

    return covers_pass, covers_fail

# Define output file paths
def build_output_paths(root: Path, args) -> Dict[str, Path]:
    return {
        "patch_code": root / "pr_code.patch",
        "run_initial": root / "run_initial.log",
        "run_test_patch": root / "run_test_patch.log",
        "log_initial": root / "log_initial.log",
        "log_test_patch": root / "log_test_patch.log",
        "parsed_initial": Path("/share-new/leikepeng/code/gen_output1") / args.repo_name / "parsed_initial.json",
        "parsed_test_patch": root / "parsed_test_patch.json",
        "diff": root / "diff_F2P.txt",
        "result_json": root / "result.json",
        "cd_patch_path": root / "cd_patch_path.patch"
    }

def load_patch(text_arg, file_arg, default_text=""):
    if file_arg: 
        with open(file_arg, "r", encoding="utf-8") as f:
            return f.read()
    if text_arg: 
        return codecs.decode(text_arg, "unicode_escape")
    return codecs.decode(default_text, "unicode_escape")

# Main execution flow
def main(args: argparse.Namespace) -> None:
    repo_name = args.repo_name
    out_root = Path(args.work_root)
    out_root.mkdir(parents=True, exist_ok=True)
    paths = build_output_paths(out_root, args)

    image_tag = args.image_tag

    ensure_container(image_tag, args.container_name, out_root)

    code_patch_text = load_patch(args.code_patch, args.code_patch_file, default_text="CODE_PATCH_DEFAULT")
    pre_test_cmd = Path(args.test_cmd_file).read_text(encoding="utf-8")
    test_cmd = args.test_cmd

    write_text(paths["patch_code"], code_patch_text)

    docker_cp_to_container(args.container_name, paths["patch_code"], "/patches/pr_code.patch")
    docker_cp_to_container(args.container_name, Path(args.cd_patch_path), "/patches/cd_patch_path.patch")
 
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
        apply_tests=True, apply_code=True, logfile=paths["run_test_patch"],rec_logfile=paths["log_test_patch"], parsed_file=paths["parsed_test_patch"], repo_name=args.repo_name
    )
    log(f"[INFO] stage_e exit code: {rc_e}")
    
    PASS_TO_PASS, FAIL_TO_PASS = False,False
    if paths["parsed_test_patch"].exists():
        PASS_TO_PASS, FAIL_TO_PASS = check_pass_coverage(paths["parsed_test_patch"],args.pass_to_pass_file,args.fail_to_pass_file)
    parsed_files_ok = all(
        paths[k].exists() and paths[k].stat().st_size > 0
        for k in ["parsed_initial", "parsed_test_patch"]
    )
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
        "base_commit": args.base_commit,
        "run_state": run_state,
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

    parser.add_argument("--docker-tar", default="/share-new/zhangxiaojiang/swebench_verified_images/swebench_sweb.eval.x86_64.astropy_1776_astropy-12907_latest.tar", help="Path to the Docker image tar file")
    parser.add_argument("--base-commit", default="", help="Base commit hash")
    parser.add_argument("--test-cmd", default="", help="Test command")
    parser.add_argument("--repo_name", default="", help="Repository name")
    parser.add_argument("--test-cmd-file", default=None, help="Test command (file path)")

    parser.add_argument("--instance_number", default=12907, help="Instance number (used for artifact directory)")
    parser.add_argument("--work-root", default="", help="Root directory for artifacts")

    parser.add_argument("--container-name", default="astropy-12907", help="Container name")
    parser.add_argument("--image-tag", default="swebench/sweb.eval.x86_64.astropy_1776_astropy-12907", help="Image name:tag (parsed from docker load output if not provided)")

    parser.add_argument("--http-proxy", default="", help="http_proxy/HTTP_PROXY")
    parser.add_argument("--https-proxy", default="", help="https_proxy/HTTPS_PROXY")
    parser.add_argument("--no-proxy", default="", help="no_proxy/NO_PROXY")

    parser.add_argument("--tests-patch", default=None, help="External tests patch content")
    parser.add_argument("--code-patch", default=None, help="External code patch content")
    parser.add_argument("--tests-patch-file", default=None, help="Path to external tests patch file")
    parser.add_argument("--code-patch-file", default=None, help="Path to external code patch file")
    parser.add_argument("--cd_patch_path", default=None, help="Path to cd patch file")

    parser.add_argument("--pass-to-pass-file", type=str, required=True, help="JSON file containing PASS_TO_PASS list")
    parser.add_argument("--fail-to-pass-file", type=str, required=True, help="JSON file containing FAIL_TO_PASS list")

    args = parser.parse_args()
    main(args)