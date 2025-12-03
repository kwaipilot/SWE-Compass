import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

def parse_log_arrow(path: Path, min_duration: float = 0.1) -> Dict[str, float]:
    results: Dict[str, float] = {}
    if not path.exists():
        return results

    pattern = re.compile(
        r"Test\s+#\d+:\s*(\S+).*?Passed\s+([\d.]+)\s*sec",
        re.IGNORECASE
    )

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pattern.search(line)
            if not m:
                continue
            test_name = m.group(1).strip()
            try:
                t = float(m.group(2))
            except ValueError:
                continue
            if t >= min_duration:
                results[test_name] = t
    return results

def parse_log_checkstyle(path: Path) -> Dict[str, float]:
    results = {}

    pattern = re.compile(
        r"Tests run:\s+\d+,\s+Failures:\s+(\d+),\s+Errors:\s+(\d+),\s+Skipped:\s+\d+,\s+Time elapsed:\s+([\d.]+)\s+s\s+--\s+in\s+(\S+)"
    )

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pattern.search(line)
            if not m:
                continue

            failures = int(m.group(1))
            errors = int(m.group(2))
            elapsed = float(m.group(3))
            classname = m.group(4)

            if failures == 0 and errors == 0 and elapsed >= 0.01:
                results[classname] = elapsed

    return results

def parse_log_kiota(path: Path) -> Dict[str, int]:
    results = {}

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("Passed "):
                continue

            if "[" not in line or "]" not in line:
                continue

            name = line[len("Passed "):line.rfind("[")].strip()
            time_part = line[line.rfind("[")+1 : line.rfind("]")].strip()

            if time_part.startswith("<"):
                continue

            if time_part.endswith("ms"):
                time_value = time_part.replace("ms", "").strip()
                try:
                    ms = int(time_value)
                except ValueError:
                    continue

                if ms >= 10:
                    results[name] = ms

    return results

def parse_log_matrixone(path: Path, min_duration: float = 0.1) -> Dict[str, float]:
    results: Dict[str, float] = {}
    if not path.exists():
        return results

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if "--- PASS" not in line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            output = obj.get("Output", "")
            if not output.startswith("--- PASS"):
                continue

            parts = output.strip().split()
            if len(parts) >= 3 and parts[1] == "PASS:":
                test_name = parts[2]
                if "(" in output and ")" in output:
                    try:
                        time_str = output.split("(")[-1].split(")")[0].rstrip("s")
                        t = float(time_str)
                    except ValueError:
                        t = None
                    if t is not None and t >= min_duration:
                        results[test_name] = t
    return results

def parse_log_mypy_po(path: Path, min_duration: float = 0.01) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not path.exists():
        return result

    pattern = re.compile(
        r"\[success\]\s+.*?\s+(mypy/.*?):\s*([0-9.]+)s",
        re.IGNORECASE,
    )

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            m = pattern.search(line)
            if not m:
                continue
            full_name = m.group(1).strip()
            try:
                t = float(m.group(2))
            except ValueError:
                continue
            if t >= min_duration:
                result[full_name] = t

    return result

def parse_log_protobuf(path: Path) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not path.exists():
        return result

    pattern = re.compile(r"\[\s*OK\s*\]\s+(\S+)\s+\((\d+)\s*ms\)", re.IGNORECASE)

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            m = pattern.search(line)
            if not m:
                continue
            name = m.group(1).strip()
            try:
                ms = int(m.group(2))
                sec = ms / 1000.0
            except ValueError:
                continue

            if sec > 0.01:
                result[name] = sec

    return result

def parse_log_svelte(path: Path) -> Dict[str, int]:
    results = {}
    pattern = r'^\s*ok\s+\d+\s+-\s+(.+?)\s+#\s+time=(\d+(?:\.\d+)?)ms'

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()

            if '.ts' in line or '.js' in line:
                continue

            match = re.match(pattern, line)
            if match:
                test_name = match.group(1).strip()
                time_ms_str = match.group(2)
                time_ms = int(float(time_ms_str))
                if time_ms >= 10:
                    results[test_name] = time_ms

    return results

def parse_log_systemd(path: Path) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not path.exists():
        return result

    pattern = re.compile(
        r"^\s*\d+/\d+\s+systemd:(.+?)\s+(OK|FAIL|SKIP|TIMEOUT)\s+([0-9.]+)s",
        re.IGNORECASE,
    )

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = pattern.match(line)
            if not m:
                continue
            name = m.group(1).strip()
            status = m.group(2).upper()
            try:
                t = float(m.group(3))
            except ValueError:
                t = None
            if status == "OK" and t is not None:
                result[name] = t

    return result

def get_parse_log(repo_key: str):
    normalized = repo_key.replace("-", "_")
    func_name = f"parse_log_{normalized}"
    func = globals().get(func_name)
    if callable(func):
        return func
    print("Parse Not Found!")
    return None
