#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import subprocess
from pathlib import Path
from tqdm import tqdm
import concurrent.futures
from collections import defaultdict
import uuid
import time
from typing import Dict, List
from swecompass.evaluators.code_understanding.code_understanding import run_code_understanding
from swecompass.evaluators.unit_test_generation.unit_test import evaluate

CURRENT_DIR = Path(__file__).resolve().parent

def eval_performance_optimization(data: dict, work_root: str, tmp_dir: str, proxy: str) -> int:
    Evaluater = CURRENT_DIR / "performance_optimization" / "eval_executor.py"
    repo = data.get("repo_key", "")
    pr_number = str(data.get("pull_number", ""))
    instance_id = data.get("instance_id", "")
    work_dir = Path(work_root) / instance_id 

    lock_file = work_dir / ".lock"
    result_file = work_dir / "result.json"

    if work_dir.exists():
        print(f"[SKIP] {repo} PR #{pr_number} 已有 目录，跳过。")
        return 0
    if result_file.exists():
        print(f"[SKIP] {repo} PR #{pr_number} 已有 result.json，跳过。")
        return 0
    if lock_file.exists():
        print(f"[SKIP] {repo} PR #{pr_number} 正在被其他节点执行，跳过。")
        return 0

    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        lock_file.write_text(f"{os.uname().nodename} {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e:
        print(f"[WARN] 无法创建锁文件 {lock_file}: {e}")

    TMP_DIR = Path(tmp_dir)
    uid = f"{repo}-{pr_number}-{uuid.uuid4().hex[:8]}"
    test_patch_file   = TMP_DIR / f"test_{uid}.patch"
    code_patch_file   = TMP_DIR / f"code_{uid}.patch"
    test_cmd_file     = TMP_DIR / f"pre_test_cmd_{uid}.sh"
    pass_to_pass_file = TMP_DIR / f"pass_to_pass_{uid}.json"
    fail_to_pass_file = TMP_DIR / f"fail_to_pass_{uid}.json"

    try:
        if "test_patch" in data:
            test_patch_file.write_text(str(data["test_patch"]), encoding="utf-8")
        if "model_patch" in data:
            code_patch_file.write_text(str(data["model_patch"]), encoding="utf-8")
        if "pre_test_cmd" in data:
            test_cmd_file.write_text(f"{proxy}; {data['pre_test_cmd']}", encoding="utf-8")
        if "PASS_TO_PASS" in data:
            json.dump(data["PASS_TO_PASS"], open(pass_to_pass_file, "w", encoding="utf-8"), ensure_ascii=False)
        if "FAIL_TO_PASS" in data:
            json.dump(data["FAIL_TO_PASS"], open(fail_to_pass_file, "w", encoding="utf-8"), ensure_ascii=False)

        cmd = [
            sys.executable, str(Evaluater),
            "--base-commit", data.get("base_commit", ""),
            "--test-cmd-file", str(test_cmd_file),
            "--test-cmd", data.get("test_cmd", ""),
            "--repo_name", repo,
            "--pr-number", pr_number,
            "--work-root", str(work_dir),
            "--container-name", f"{repo}-{pr_number}-{time.strftime('%Y%m%d-%H%M%S')}",
            "--image-tag", "swecompass/eval:" + data.get("repo_key", ""),
            "--tests-patch-file", str(test_patch_file),
            "--code-patch-file", str(code_patch_file),
            "--pass-to-pass-file", str(pass_to_pass_file),
            "--fail-to-pass-file", str(fail_to_pass_file),
        ]

        print(f"[RUN] {' '.join(cmd)}")
        return subprocess.run(cmd).returncode

    finally:
        for f in [test_patch_file, code_patch_file, test_cmd_file, pass_to_pass_file, fail_to_pass_file]:
            try:
                if f.exists():
                    f.unlink()
            except Exception as e:
                print(f"[WARN] 删除临时文件 {f} 失败: {e}")

        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception as e:
            print(f"[WARN] 删除锁文件 {lock_file} 失败: {e}")

def eval_configuration_deployment(data: dict, work_root: str, tmp_dir: str, proxy: str) -> int:
    Evaluater = CURRENT_DIR / "configuration_deployment" / "eval_executor.py"
    repo = data.get("repo_key", "")
    instance_id = str(data.get("instance_id", ""))
    work_dir = Path(work_root) / instance_id

    work_dir_parsed_test = work_dir / 'parsed_test_patch.json'
    if work_dir_parsed_test.exists():
        print(f"[SKIP] {instance_id} 已存在，跳过")
        return 0

    TMP_DIR = Path(tmp_dir)
    uid = f"{data.get('repo_key','')}-{data.get('instance_id','')}-{uuid.uuid4().hex[:8]}"
    test_cmd_file = TMP_DIR / f"pre_test_cmd_{uid}.sh"
    test_patch_file   = TMP_DIR / f"test_{uid}.patch"
    code_patch_file   = TMP_DIR / f"code_{uid}.patch"
    pass_to_pass_file = TMP_DIR / f"pass_to_pass_{uid}.json"
    fail_to_pass_file = TMP_DIR / f"fail_to_pass_{uid}.json"

    if "test_patch" in data:
        test_patch_file.write_text(str(data["test_patch"]), encoding="utf-8")
    if "model_patch" in data:
        code_patch_file.write_text(str(data["model_patch"]), encoding="utf-8")
    if "pre_test_cmd" in data:
        test_cmd_file.write_text(f"{proxy}; {data['pre_test_cmd']}", encoding="utf-8")
    if "PASS_TO_PASS" in data:
        json.dump(data["PASS_TO_PASS"], open(pass_to_pass_file, "w", encoding="utf-8"), ensure_ascii=False)
    if "FAIL_TO_PASS" in data:
        json.dump(data["FAIL_TO_PASS"], open(fail_to_pass_file, "w", encoding="utf-8"), ensure_ascii=False)

    cmd = [
        sys.executable, str(Evaluater),
        "--base-commit", data.get("base_commit", ""),
        "--instance_number", instance_id,
        "--test-cmd", data.get("test_cmd", ""),
        "--repo_name", data.get("repo_key", ""),
        "--work-root", str(work_dir),
        "--container-name", f"swecompass-{data.get('repo_key', '')}-{instance_id}",
        "--image-tag", "swecompass/eval:" + data.get("repo_key", ""),
        "--code-patch-file", str(code_patch_file),
        "--test-cmd-file", test_cmd_file,
        "--cd_patch_path", str(test_patch_file),
        "--pass-to-pass-file", str(pass_to_pass_file),
        "--fail-to-pass-file", str(fail_to_pass_file),
        ]
    print(cmd)
    print(f"[RUN] {instance_id}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if test_cmd_file.exists():
        test_cmd_file.unlink()
    
    return result.returncode
    
def eval_selected(data: dict, work_root: str, tmp_dir: str, proxy: str) -> int:
    Evaluater = CURRENT_DIR / "selected" / "eval_executor.py"
    repo = data.get("repo_key", "")
    pr_number = str(data.get("pull_number", ""))
    instance_id = data.get("instance_id", "")
    work_dir = Path(work_root) / instance_id 

    lock_file = work_dir / ".lock"
    result_file = work_dir / "result.json"

    if work_dir.exists():
        print(f"[SKIP] {repo} PR #{pr_number} 已有 目录，跳过。")
        return 0
    if result_file.exists():
        print(f"[SKIP] {repo} PR #{pr_number} 已有 result.json，跳过。")
        return 0
    if lock_file.exists():
        print(f"[SKIP] {repo} PR #{pr_number} 正在被其他节点执行，跳过。")
        return 0

    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        lock_file.write_text(f"{os.uname().nodename} {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e:
        print(f"[WARN] 无法创建锁文件 {lock_file}: {e}")

    TMP_DIR = Path(tmp_dir)
    uid = f"{repo}-{pr_number}-{uuid.uuid4().hex[:8]}"
    test_patch_file   = TMP_DIR / f"test_{uid}.patch"
    code_patch_file   = TMP_DIR / f"code_{uid}.patch"
    test_cmd_file     = TMP_DIR / f"pre_test_cmd_{uid}.sh"
    pass_to_pass_file = TMP_DIR / f"pass_to_pass_{uid}.json"
    fail_to_pass_file = TMP_DIR / f"fail_to_pass_{uid}.json"

    try:
        if "test_patch" in data:
            test_patch_file.write_text(str(data["test_patch"]), encoding="utf-8")
        if "model_patch" in data:
            code_patch_file.write_text(str(data["model_patch"]), encoding="utf-8")
        if "pre_test_cmd" in data:
            test_cmd_file.write_text(f"{proxy}; {data['pre_test_cmd']}", encoding="utf-8")
        if "PASS_TO_PASS" in data:
            json.dump(data["PASS_TO_PASS"], open(pass_to_pass_file, "w", encoding="utf-8"), ensure_ascii=False)
        if "FAIL_TO_PASS" in data:
            json.dump(data["FAIL_TO_PASS"], open(fail_to_pass_file, "w", encoding="utf-8"), ensure_ascii=False)

        cmd = [
            sys.executable, str(Evaluater),
            "--base-commit", data.get("base_commit", ""),
            "--test-cmd-file", str(test_cmd_file),
            "--test-cmd", data.get("test_cmd", ""),
            "--repo_name", repo,
            "--pr-number", pr_number,
            "--work-root", str(work_dir),
            "--container-name", f"{repo}-{pr_number}-{time.strftime('%Y%m%d-%H%M%S')}",
            "--image-tag", "swecompass/eval:" + data.get("repo_key", ""),
            "--tests-patch-file", str(test_patch_file),
            "--code-patch-file", str(code_patch_file),
            "--pass-to-pass-file", str(pass_to_pass_file),
            "--fail-to-pass-file", str(fail_to_pass_file),
        ]

        print(f"[RUN] {' '.join(cmd)}")
        return subprocess.run(cmd).returncode

    finally:
        for f in [test_patch_file, code_patch_file, test_cmd_file, pass_to_pass_file, fail_to_pass_file]:
            try:
                if f.exists():
                    f.unlink()
            except Exception as e:
                print(f"[WARN] 删除临时文件 {f} 失败: {e}")

        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception as e:
            print(f"[WARN] 删除锁文件 {lock_file} 失败: {e}")

def eval_code_understanding(data: Dict, log_dir: str, model_name:str, api_key: str, base_url: str = ""):
    run_code_understanding(data, log_dir, model_name, api_key, base_url)

def eval_unit_test_generation(data: Dict, log_dir: str):
    evaluate(data, log_dir)
