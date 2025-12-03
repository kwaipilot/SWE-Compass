import re
import json
import xml.etree.ElementTree as ET

def parse_log_systemd(log: str) -> dict[str, dict]:
    # Parse systemd meson test output
    status_map = {}
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

    return status_map

def parse_log_xnnpack(log: str) -> dict[str, str]:
    # Parse XNNPACK test logs
    status_map = {}
    pattern = re.compile(r"\d+/\d+\s+Test\s+#\d+:\s+(\S+).*?sec", re.IGNORECASE)

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

    return status_map

def parse_log_bitcoin_old(log: str) -> dict[str, str]:
    # Parse legacy Bitcoin Boost.Test logs
    results = {}
    lines = log.splitlines()
    suite_pattern = re.compile(r'Test suite "([^"]+)" has (\w+)', re.IGNORECASE)
    case_pattern = re.compile(r'(\d+)\s+test cases out of\s+(\d+)\s+passed', re.IGNORECASE)

    i = 0
    while i < len(lines):
        line = lines[i]
        m = suite_pattern.search(line)
        if m:
            suite_name = m.group(1)
            state_word = m.group(2).upper()

            status = "UNKNOWN"
            if state_word == "PASSED":
                status = "PASSED"
            elif state_word == "FAILED":
                status = "FAILED"
            elif state_word == "SKIPPED":
                status = "SKIPPED"

            if i + 1 < len(lines):
                n = case_pattern.search(lines[i + 1])
                if n:
                    passed, total = int(n.group(1)), int(n.group(2))
                    if passed == total:
                        status = "PASSED"
                    else:
                        status = "FAILED"

            results[suite_name] = status
        i += 1

    return results

def parse_log_bitcoin(log: str) -> dict[str, str]:
    # Parse Bitcoin test logs
    status_map = {}
    pattern = re.compile(r"\d+/\d+\s+Test\s+#\d+:\s+(\S+).*?sec", re.IGNORECASE)

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

    return status_map

def parse_log_godot(log: str) -> dict[str, str]:
    # Extract XML block from log and parse
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
    return status_map

def parse_log_protobuf(log: str) -> dict[str, str]:
    # Parse GoogleTest style logs
    status_map = {}
    seen = set()

    pattern = re.compile(r"\[\s*(OK|PASSED|FAILED|SKIPPED)\s*\]\s+(\S+)")

    for line in log.splitlines():
        m = pattern.search(line)
        if not m:
            continue

        raw_status = m.group(1).strip()
        name = m.group(2).strip()

        if name.isdigit():
            continue

        status = "PASSED" if raw_status == "OK" else raw_status

        if name not in seen:
            status_map[name] = status
            seen.add(name)

    return status_map

def parse_log_matrixone(log: str) -> dict[str, str]:
    test_results = {}
    
    lines = log.strip().split('\n')
    
    for line in lines:
        if not line.strip():
            continue
            
        try:
            if line.startswith('{"Time"'):
                json_data = json.loads(line)
                
                if 'Action' in json_data and 'Test' in json_data:
                    action = json_data['Action'].lower()
                    test_name = json_data['Test']
                    
                    if action == 'pass':
                        test_results[test_name] = 'PASSED'
                    elif action == 'fail':
                        test_results[test_name] = 'FAILED'
                    elif action == 'skip':
                        test_results[test_name] = 'SKIPPED'
                        
                elif 'Action' in json_data and json_data['Action'].lower() == 'skip' and 'Package' in json_data:
                    package_name = json_data['Package'].split('/')[-1]
                    test_results[f"Package_{package_name}"] = 'SKIPPED'
                    
        except (json.JSONDecodeError, KeyError):
            continue
            
        if '--- PASS:' in line:
            match = re.search(r'--- PASS:\s+(\w+)', line)
            if match:
                test_name = match.group(1)
                if test_name not in test_results:
                    test_results[test_name] = 'PASSED'
                    
        elif '--- FAIL:' in line:
            match = re.search(r'--- FAIL:\s+(\w+)', line)
            if match:
                test_name = match.group(1)
                if test_name not in test_results:
                    test_results[test_name] = 'FAILED'
                    
        elif '--- SKIP:' in line:
            match = re.search(r'--- SKIP:\s+(\w+)', line)
            if match:
                test_name = match.group(1)
                if test_name not in test_results:
                    test_results[test_name] = 'SKIPPED'
    
    return test_results

def parse_log_eslint(log: str) -> dict[str, str]:
    
    status_map = {}
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
    
    return status_map

def parse_log_svelte(log: str) -> dict[str, str]:
    status_map = {}
    
    for line in log.splitlines():
        line = line.strip()

        if line.startswith('✓'):
            parts = line.split(' ', 1)
            if len(parts) > 1:
                test_path = parts[1]
                test_path = re.sub(r'\s+\d+ms$', '', test_path)
                status_map[test_path] = "PASSED"
        
        elif line.startswith('FAIL'):
            parts = line.split(' ', 1)
            if len(parts) > 1:
                test_path = parts[1].split('[')[0].strip()
                test_path = re.sub(r'\s+\d+ms$', '', test_path)
                status_map[test_path] = "FAILED"
    
    return status_map

def parse_log_dgs_framework(log: str) -> dict[str, str]:

    import re
    
    status_map = {}

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
    
    return status_map

def parse_log_graphql_kotlin(log: str) -> dict[str, str]:

    import re
    
    status_map = {}

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
    
    return status_map

def parse_log_kotlinpoet(log: str) -> dict[str, str]:
    # Parse DGS style logs
    import re
    
    status_map = {}
    
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
    
    return status_map

def parse_log_keras(log: str) -> dict[str, str]:  
    # Parse Keras test logs
    results = {}
    
    pattern = re.compile(
        r'(keras/[^:]+::[^:]+::[^\s]+)\s+(PASSED|FAILED|SKIPPED)',
        re.MULTILINE
    )
    
    matches = pattern.findall(log)
    
    for test_name, status in matches:
        results[test_name.strip()] = status.strip()
    
    return results

def parse_log_mypy(log: str) -> dict[str, str]:
    # Parse mypy test logs

    results = {}
    
    test_result_pattern = re.compile(
        r'\[gw\d+\]\s+\[\s*\d+%\]\s+(PASSED|FAILED|SKIPPED)\s+(.+)'
    )
    
    lines = log.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        match = test_result_pattern.search(line)
        if match:
            status = match.group(1)
            test_name = match.group(2).strip()
            
            results[test_name] = status
    
    return results
    
def parse_log_cargo(log: str) -> dict[str, str]:
    # Parse Rust/Cargo test logs
    status_map = {}
    
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
    
    return status_map

def parse_log_rust_analyzer(log: str) -> dict[str, str]:
    # Parse Rust Analyzer test logs
    status_map = {}
    
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
    
    return status_map

def parse_log_rust_clippy(log: str) -> dict[str, str]:
    # Parse Rust Clippy test logs
    status_map = {}
    
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
    
    return status_map

def parse_log_kiota(log: str) -> dict[str, str]:
    status_map = {}
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
    return status_map

def parse_log_runelite(log: str) -> dict[str, str]:
    status_map = {}
    pattern = re.compile(r".*?Failures:\s+(\d+).*?Errors:\s+(\d+).*?Skipped:\s+(\d+).*?(net\..*?$)", re.IGNORECASE)
    for line in log.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        if int(m.group(1)) > 0:
                status = 'FAILED'
        elif int(m.group(2)) > 0:
            status = "ERROR"
        elif int(m.group(3)) > 0:
            status = "SKIPPED"
        else:
            status = "PASSED"
        name = m.group(4)
        status_map[name] = status
    return status_map

def parse_log_google_cloud_java(log: str) -> dict[str, str]:
    status_map = {}
    pattern = re.compile(r".*?Failures:\s+(\d+).*?Errors:\s+(\d+).*?Skipped:\s+(\d+).*?(com\..*?$)", re.IGNORECASE)
    for line in log.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        if int(m.group(1)) > 0:
                status = 'FAILED'
        elif int(m.group(2)) > 0:
            status = "ERROR"
        elif int(m.group(3)) > 0:
            status = "SKIPPED"
        else:
            status = "PASSED"
        name = m.group(4)
        status_map[name] = status
    return status_map

def parse_log_openra(log: str) -> dict[str, str]:
    status_map = {}
    pattern = re.compile(r"\s+\w+\s+(.*?)\s+\[\d+\s+ms\]$", re.IGNORECASE)
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
    return status_map

def parse_log_checkstyle(log: str) -> dict[str, str]:
    status_map = {}
    pattern = re.compile(r".*?Failures:\s+(\d+).*?Errors:\s+(\d+).*?Skipped:\s+(\d+).*?(com\..*?$)", re.IGNORECASE)
    for line in log.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        if int(m.group(1)) > 0:
                status = 'FAILED'
        elif int(m.group(2)) > 0:
            status = "ERROR"
        elif int(m.group(3)) > 0:
            status = "SKIPPED"
        else:
            status = "PASSED"
        name = m.group(4)
        status_map[name] = status
    return status_map

def parse_log_mpv(log: str) -> dict[str, dict]:
    # Parse mpv meson test output
    status_map = {}
    pattern = re.compile(r"^\s*\d+/\d+\s+(.+?)\s+(OK|FAIL|SKIP|TIMEOUT|Expected\s+Fail)\b", re.IGNORECASE)

    for line in log.splitlines():
        m = pattern.match(line)
        if not m:
            continue

        name = m.group(1).strip()
        result = m.group(2).upper()

        if result == "OK":
            status = "PASSED"
        elif result in ("FAIL", "TIMEOUT"):
            status = "FAILED"
        elif result == "SKIP":
            status = "SKIPPED"
        elif result.startswith("EXPECTED FAIL"):
            status = "PASSED" 
        else:
            status = "UNKNOWN"

        status_map[name] = status
    return status_map
    
def parse_log_dropwizard(log: str) -> dict[str, str]:
    status_map = {}
    pattern = re.compile(r"\[INFO\]\s+(\w+)\s+\.+\s+\w+\s+\[", re.IGNORECASE)
    for line in log.splitlines():
        m = pattern.search(line)
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
    return status_map

def parse_log_deno(log: str) -> dict[str, str]:
    import re
    
    status_map = {}

    cmake_pattern = re.compile(
        r"(?:\[[\w\-\s\.]+\]\s*)?--\s*Performing\s+Test\s+(\S+)(?:\s*-\s*(\w+))?",
        re.IGNORECASE
    )

    rust_test_pattern = re.compile(
        r"test\s+([\w:]+)\s*\.\.\.\s*(\w+)",
        re.IGNORECASE
    )

    running_pattern = re.compile(
        r"([\w:]+)\s*\.\.\.\s*(ok|FAILED|ignored|test\s+result)",
        re.IGNORECASE
    )
    
    for line in log.splitlines():
        line = line.strip()
        if not line:
            continue
            
        cmake_match = cmake_pattern.search(line)
        if cmake_match:
            test_name = cmake_match.group(1)
            status = cmake_match.group(2) if cmake_match.group(2) else "UNKNOWN"
            
            if status.lower() in ["success", "succeeded", "passed", "pass", "ok"]:
                status_map[test_name] = "PASSED"
            elif status.lower() in ["failed", "fail", "failure", "error"]:
                status_map[test_name] = "FAILED"
            elif status.lower() in ["skipped", "skip", "ignored", "disable", "disabled"]:
                status_map[test_name] = "SKIPPED"
            else:
                if "success" in line.lower() or "passed" in line.lower():
                    status_map[test_name] = "PASSED"
                elif "fail" in line.lower() or "error" in line.lower():
                    status_map[test_name] = "FAILED"
                elif "skip" in line.lower() or "ignore" in line.lower():
                    status_map[test_name] = "SKIPPED"
                else:
                    status_map[test_name] = "UNKNOWN"
            continue
            
        rust_match = rust_test_pattern.search(line)
        if rust_match:
            test_name = rust_match.group(1)
            status = rust_match.group(2).lower()
            
            if status in ["ok", "passed", "pass"]:
                status_map[test_name] = "PASSED"
            elif status in ["failed", "fail", "failure"]:
                status_map[test_name] = "FAILED"
            elif status in ["ignored", "skip", "skipped"]:
                status_map[test_name] = "SKIPPED"
            elif status in ["error", "panic", "panicked"]:
                status_map[test_name] = "ERROR"
            else:
                status_map[test_name] = "UNKNOWN"
            continue
            
        running_match = running_pattern.search(line)
        if running_match and "test result" not in line.lower():
            test_name = running_match.group(1)
            status = running_match.group(2).lower()
            
            if status == "ok":
                status_map[test_name] = "PASSED"
            elif status == "failed":
                status_map[test_name] = "FAILED"
            elif status == "ignored":
                status_map[test_name] = "SKIPPED"
    
    error_pattern = re.compile(
        r"(?:error|panic|thread\s+'[\w\s]+'\s+panicked|SIGABRT|assertion\s+failed)",
        re.IGNORECASE
    )
    
    for line in log.splitlines():
        if error_pattern.search(line):
            for test_name in status_map:
                if test_name in line:
                    status_map[test_name] = "ERROR"
                    break
    
    return status_map

def parse_log_ort(log: str) -> dict[str, str]:
    # Parse ORT/DGS log format
    import re
    
    status_map = {}
    
    pattern = re.compile(
        r'^([\w.]+)\s*>\s*(.+?)\s+(PASSED|FAILED|STARTED|SKIPPED|ERROR)$',
        re.MULTILINE
    )
    
    matches = pattern.findall(log)
    
    for match in matches:
        class_name = match[0]
        method_desc = match[1]
        status = match[2]
        
        if status != 'STARTED':
            test_key = f"{class_name} > {method_desc}"
            status_map[test_key] = status
    
    return status_map

def parse_log_shardingsphere(log: str) -> dict[str, str]:

    status_map = {}
    current_test_class = None
    
    for line in log.splitlines():
        line = line.strip()

        running_match = re.match(r"\[INFO\]\s+Running\s+(.+)", line)
        if running_match:
            current_test_class = running_match.group(1)
            continue

        detailed_result_match = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+).*?--\s*in\s+(.+)", line)
        if detailed_result_match:
            tests_run = int(detailed_result_match.group(1))
            failures = int(detailed_result_match.group(2))
            errors = int(detailed_result_match.group(3))
            skipped = int(detailed_result_match.group(4))
            test_class = detailed_result_match.group(5)

            if errors > 0:
                status = "ERROR"
            elif failures > 0:
                status = "FAILED"
            elif skipped == tests_run and tests_run > 0:  # 全部跳过
                status = "SKIPPED"
            elif tests_run > 0:
                status = "PASSED"
            else:
                status = "UNKNOWN"
                
            status_map[test_class] = status
            continue

        module_result_match = re.search(r"^\[INFO\]\s+Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)\s*$", line)
        if module_result_match:
            tests_run = int(module_result_match.group(1))
            failures = int(module_result_match.group(2))
            errors = int(module_result_match.group(3))
            skipped = int(module_result_match.group(4))
            
            module_key = "MODULE_SUMMARY"
            if errors > 0:
                status = "ERROR"
            elif failures > 0:
                status = "FAILED"
            elif skipped == tests_run and tests_run > 0:
                status = "SKIPPED"
            elif tests_run > 0:
                status = "PASSED"
            else:
                status = "UNKNOWN"
                
            status_map[module_key] = status
            continue

        method_match = re.match(r"(\w+)\([^)]+\)\s+Time elapsed:.*?<<<\s*(FAILURE|ERROR)!", line)
        if method_match:
            method_name = method_match.group(1)
            failure_type = method_match.group(2)
            test_key = f"{current_test_class}::{method_name}" if current_test_class else method_name
            status_map[test_key] = "FAILED" if failure_type == "FAILURE" else "ERROR"
            continue

        if "[ERROR]" in line and "Failed to execute goal" in line:
            status_map["BUILD_ERROR"] = "ERROR"
            continue
            
        if "[ERROR]" in line and "COMPILATION ERROR" in line:
            status_map["COMPILATION_ERROR"] = "ERROR"
            continue

        if "[INFO]" in line and "No tests to run" in line:
            status_map["NO_TESTS"] = "SKIPPED"
            continue

    return status_map

def parse_log_camel(log: str) -> dict[str, str]:

    status_map = {}
    current_test_class = None
    
    for line in log.splitlines():
        line = line.strip()

        running_match = re.match(r"\[INFO\]\s+Running\s+(.+)", line)
        if running_match:
            current_test_class = running_match.group(1)
            continue

        detailed_result_match = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+).*?--\s*in\s+(.+)", line)
        if detailed_result_match:
            tests_run = int(detailed_result_match.group(1))
            failures = int(detailed_result_match.group(2))
            errors = int(detailed_result_match.group(3))
            skipped = int(detailed_result_match.group(4))
            test_class = detailed_result_match.group(5)

            if errors > 0:
                status = "ERROR"
            elif failures > 0:
                status = "FAILED"
            elif skipped == tests_run and tests_run > 0:
                status = "SKIPPED"
            elif tests_run > 0:
                status = "PASSED"
            else:
                status = "UNKNOWN"
                
            status_map[test_class] = status
            continue

        module_result_match = re.search(r"^\[INFO\]\s+Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)\s*$", line)
        if module_result_match:
            tests_run = int(module_result_match.group(1))
            failures = int(module_result_match.group(2))
            errors = int(module_result_match.group(3))
            skipped = int(module_result_match.group(4))

            module_key = "MODULE_SUMMARY"
            if errors > 0:
                status = "ERROR"
            elif failures > 0:
                status = "FAILED"
            elif skipped == tests_run and tests_run > 0:
                status = "SKIPPED"
            elif tests_run > 0:
                status = "PASSED"
            else:
                status = "UNKNOWN"
                
            status_map[module_key] = status
            continue

        method_match = re.match(r"(\w+)\([^)]+\)\s+Time elapsed:.*?<<<\s*(FAILURE|ERROR)!", line)
        if method_match:
            method_name = method_match.group(1)
            failure_type = method_match.group(2)
            test_key = f"{current_test_class}::{method_name}" if current_test_class else method_name
            status_map[test_key] = "FAILED" if failure_type == "FAILURE" else "ERROR"
            continue

        if "[ERROR]" in line and "Failed to execute goal" in line:
            status_map["BUILD_ERROR"] = "ERROR"
            continue

        if "[ERROR]" in line and "COMPILATION ERROR" in line:
            status_map["COMPILATION_ERROR"] = "ERROR"
            continue

        if "[INFO]" in line and "No tests to run" in line:
            status_map["NO_TESTS"] = "SKIPPED"
            continue

    return status_map

def parse_log_generator_jhipster(log: str) -> dict[str, str]:

    status_map = {}
    context_stack = []

    failed_test_regex = re.compile(r'^\s*\d+\)')

    for line in log.splitlines():

        stripped_line = line.lstrip(' ')
        if not stripped_line:
            continue
        
        indentation = len(line) - len(stripped_line)

        while context_stack and indentation <= context_stack[-1][0]:
            context_stack.pop()

        if stripped_line.startswith('✔ '):

            test_name = stripped_line.lstrip('✔ ').split('(')[0].strip()
            

            path_parts = [name for _, name in context_stack] + [test_name]
            full_test_name = ' :: '.join(path_parts)
            status_map[full_test_name] = 'PASSED'

        elif failed_test_regex.match(stripped_line):

            test_name = stripped_line.split(')', 1)[1].strip()

            path_parts = [name for _, name in context_stack] + [test_name]
            full_test_name = ' :: '.join(path_parts)
            status_map[full_test_name] = 'FAILED'

        elif not re.search(r'^\d+\s+(passing|pending|failing)', stripped_line) and \
             not stripped_line.startswith(('at ', 'Error:', 'AssertionError', 'TypeError', '+ expected', '- actual')):

            if stripped_line.startswith(('>', '=', 'npm ')):
                continue

            context_stack.append((indentation, stripped_line))
            
    return status_map

def parse_log_great_expectations(log: str) -> dict[str, str]:

    status_map = {}

    ansi_escape_pattern = re.compile(r'\x1b\[\d+m')

    status_words = {'PASSED', 'FAILED', 'SKIPPED', 'XFAIL', 'XPASS', 'ERROR'}

    current_test_path = None

    for line in log.splitlines():

        clean_line = ansi_escape_pattern.sub('', line).strip()
        if not clean_line:
            continue

        if '::' in clean_line:

            parts = clean_line.split()
            path_parts = []
            found_status = False
            for part in parts:
                if part in status_words:
                    found_status = True
                    break
                path_parts.append(part)
            
            potential_path = ' '.join(path_parts)

            if '::' in potential_path:
                current_test_path = potential_path.strip()

        status = None
        for word in clean_line.split():
            if word in status_words:
                status = word
                break

        if status and current_test_path:
            status_map[current_test_path] = status

            current_test_path = None
            
    return status_map

def parse_log_scipy(log: str) -> dict[str, str]:

    status_map = {}
    
    for line in log.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        status = None
        status_index = -1
        for i, part in enumerate(parts):
            if part in ['PASSED', 'FAILED', 'SKIPPED', 'XFAIL', 'XPASS', 'ERROR']:
                status = part
                status_index = i
                break
        
        if status is None:
            continue

        test_path = ' '.join(parts[:status_index]).strip()

        if '::' in test_path:
            file_path, test_name = test_path.split('::', 1)

            status_map[test_path] = status
        
    return status_map

def parse_log_prisma(log: str) -> dict[str, str]:

    status_map = {}

    status_normalization_map = {
        'PASS': 'PASSED',
        '✓': 'PASSED',
        'FAIL': 'FAILED',
        '✗': 'FAILED',
    }

    combined_pattern = re.compile(r" test:\s+(PASS|FAIL|[✓✗])\s+([\S]+\.test\.(?:ts|js))")

    for line in log.splitlines():
        match = combined_pattern.search(line)
        if match:
            indicator = match.group(1)  # "PASS", "FAIL", "✓", or "✗"
            test_path = match.group(2)

            normalized_status = status_normalization_map.get(indicator)
            
            if not normalized_status:
                continue

            if status_map.get(test_path) == 'FAILED':
                continue
            
            status_map[test_path] = normalized_status
            
    return status_map

def parse_log_sympy(log: str) -> dict[str, str]:

    status_map = {}
    current_test_file = None

    path_regex = re.compile(r"^(?P<path>.*?\.py)\[.*")

    status_regex = re.compile(r"\[(?P<status>OK|FAIL)\]\s*$")

    for line in log.splitlines():
        line = line.strip()
        if not line:
            continue

        path_match = path_regex.match(line)
        if path_match:

            current_test_file = path_match.group("path")

        status_match = status_regex.search(line)
        if status_match and current_test_file:

            status = status_match.group("status")
            status_map[current_test_file] = status

            current_test_file = None

    for k in status_map:
        if status_map[k] == "OK":
            status_map[k] = "PASSED"
        elif status_map[k] == "FAIL":
            status_map[k] = "FAILED"
        else:
            status_map[k] = "UNKNOWN"
            
    return status_map

def parse_log_arrow(log: str) -> dict[str, str]:

    status_map = {}

    pattern = re.compile(r"Test\s+#\d+:\s+(\S+).*?\b(Passed|\*\*\*Failed|Failed)\b", re.IGNORECASE)

    for line in log.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        name = m.group(1).strip()
        raw_status = m.group(2).lower()

        if "pass" in raw_status:
            status = "PASSED"
        elif "fail" in raw_status:
            status = "FAILED"
        else:
            status = "UNKNOWN"

        status_map[name] = status

    return status_map

def parse_log_webpack(log: str) -> dict[str, str]:
    status_map = {}
    
    for line in log.splitlines():
        line = line.strip()

        if line.startswith('PASS'):

            parts = line.split(' ', 1)
            if len(parts) > 1:
                test_path = parts[1].split('(')[0].strip()
                status_map[test_path] = "PASSED"
        
        elif line.startswith('FAIL'):
            parts = line.split(' ', 1)
            if len(parts) > 1:

                test_path = parts[1].split('(')[0].strip()
                status_map[test_path] = "FAILED"
    
    return status_map

def parse_log_simple_icons(log: str) -> dict[str, str]:

    status_map = {}

    sections = log.split('\n\n')

    for section in sections:

        if not section.strip():
            continue
            
        lines = section.strip().splitlines()

        if len(lines) < 2:
            continue

        test_name = lines[0].strip()

        if re.match(r'^[✔✓]|^\d+\)', test_name):
            continue

        valid_section = True
        has_failure = False
        
        for line in lines[1:]:
            stripped_line = line.strip()
            if not stripped_line:
                continue
                
            if re.match(r'^[✔✓]', stripped_line):
                continue
            elif re.match(r'^\d+\)', stripped_line):

                has_failure = True
            else:

                valid_section = False
                break

        if valid_section:
            if has_failure:
                status_map[test_name] = "FAILED"
            else:
                status_map[test_name] = "PASSED"

    return status_map

def parse_log_loki(log: str) -> dict[str, str]:
    """
    Analyze the test log text and extract test case results

    Args:
        log (str): The test log content as a string
    Returns:
        dict: Dictionary with test case names as keys and status ("PASSED", "FAILED", "SKIPPED") as values
    """
    test_results = {}
    content = log
    # Pattern for successful test packages (ok lines)
    ok_pattern = r'^ok\s+([^\s]+)\s+.*$'
    # Pattern for failed test packages (FAIL lines)
    fail_package_pattern = r'^FAIL\s+([^\s]+)\s+.*$'
    # Pattern for individual failed tests within packages
    fail_test_pattern = r'^--- FAIL: (\w+)'
    # Pattern for build failures
    build_fail_pattern = r'^FAIL\s+([^\s]+)\s+\[build failed\]'
    # Pattern for skipped/no test files
    skip_pattern = r'^\?\s+([^\s]+)\s+\[no test files\]'
    # Pattern for coverage 0.0% (essentially skipped)
    zero_coverage_pattern = r'^\s+([^\s]+)\s+coverage: 0\.0% of statements'
    lines = content.split('\n')
    
    current_package = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Check for successful packages
        ok_match = re.match(ok_pattern, line)
        if ok_match:
            package_name = ok_match.group(1)
            test_results[package_name] = "PASSED"
            current_package = package_name
            continue
        
        # Check for build failed packages
        build_fail_match = re.match(build_fail_pattern, line)
        if build_fail_match:
            package_name = build_fail_match.group(1)
            test_results[package_name] = "FAILED"
            current_package = package_name
            continue
        
        # Check for failed packages
        fail_package_match = re.match(fail_package_pattern, line)
        if fail_package_match:
            package_name = fail_package_match.group(1)
            test_results[package_name] = "FAILED"
            current_package = package_name
            continue
            
        # Check for skipped packages (no test files)
        skip_match = re.match(skip_pattern, line)
        if skip_match:
            package_name = skip_match.group(1)
            test_results[package_name] = "SKIPPED"
            continue
        
        # Check for zero coverage (essentially skipped)
        zero_coverage_match = re.match(zero_coverage_pattern, line)
        if zero_coverage_match:
            package_name = zero_coverage_match.group(1)
            # Only mark as skipped if not already marked as passed/failed
            if package_name not in test_results:
                test_results[package_name] = "SKIPPED"
            continue
        
        # Check for individual test failures within packages
        fail_test_match = re.match(fail_test_pattern, line)
        if fail_test_match and current_package:
            test_name = fail_test_match.group(1)
            full_test_name = f"{current_package}::{test_name}"
            test_results[full_test_name] = "FAILED"
    
    return test_results

def parse_log_shardingsphere(log: str) -> dict[str, str]:

    status_map = {}
    current_test_class = None
    
    for line in log.splitlines():
        line = line.strip()
        
        running_match = re.match(r"\[INFO\]\s+Running\s+(.+)", line)
        if running_match:
            current_test_class = running_match.group(1)
            continue

        detailed_result_match = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+).*?--\s*in\s+(.+)", line)
        if detailed_result_match:
            tests_run = int(detailed_result_match.group(1))
            failures = int(detailed_result_match.group(2))
            errors = int(detailed_result_match.group(3))
            skipped = int(detailed_result_match.group(4))
            test_class = detailed_result_match.group(5)
            

            if errors > 0:
                status = "ERROR"
            elif failures > 0:
                status = "FAILED"
            elif skipped == tests_run and tests_run > 0:
                status = "SKIPPED"
            elif tests_run > 0:
                status = "PASSED"
            else:
                status = "UNKNOWN"
                
            status_map[test_class] = status
            continue
            
        module_result_match = re.search(r"^\[INFO\]\s+Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)\s*$", line)
        if module_result_match:
            tests_run = int(module_result_match.group(1))
            failures = int(module_result_match.group(2))
            errors = int(module_result_match.group(3))
            skipped = int(module_result_match.group(4))

            module_key = "MODULE_SUMMARY"
            if errors > 0:
                status = "ERROR"
            elif failures > 0:
                status = "FAILED"
            elif skipped == tests_run and tests_run > 0:
                status = "SKIPPED"
            elif tests_run > 0:
                status = "PASSED"
            else:
                status = "UNKNOWN"
                
            status_map[module_key] = status
            continue

        method_match = re.match(r"(\w+)\([^)]+\)\s+Time elapsed:.*?<<<\s*(FAILURE|ERROR)!", line)
        if method_match:
            method_name = method_match.group(1)
            failure_type = method_match.group(2)
            test_key = f"{current_test_class}::{method_name}" if current_test_class else method_name
            status_map[test_key] = "FAILED" if failure_type == "FAILURE" else "ERROR"
            continue

        if "[ERROR]" in line and "Failed to execute goal" in line:
            status_map["BUILD_ERROR"] = "ERROR"
            continue

        if "[ERROR]" in line and "COMPILATION ERROR" in line:
            status_map["COMPILATION_ERROR"] = "ERROR"
            continue

        if "[INFO]" in line and "No tests to run" in line:
            status_map["NO_TESTS"] = "SKIPPED"
            continue

    return status_map

def parse_log_frr(log: str) -> dict[str, str]:

    import re
    status_map = {}
    
    for line in log.splitlines():
        line = line.strip()

        pytest_match = re.match(r'^(.+?::.+?)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS|TODO)\s+\[\s*\d+%\](?:\s*|$)', line)
        if pytest_match:
            test_case = pytest_match.group(1)
            status = pytest_match.group(2)

            if status == "PASSED":
                status_map[test_case] = "PASSED"
            elif status == "FAILED":
                status_map[test_case] = "FAILED"
            elif status == "SKIPPED":
                status_map[test_case] = "SKIPPED"
            elif status == "ERROR":
                status_map[test_case] = "ERROR"
            else:
                status_map[test_case] = status
            continue

        summary_match = re.search(r'===\s*(\d+)\s+passed,\s*(\d+)\s+failed,\s*(\d+)\s+skipped', line, re.IGNORECASE)
        if summary_match:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2)) if summary_match.group(2) else 0
            skipped = int(summary_match.group(3)) if summary_match.group(3) else 0
            
            if failed > 0:
                status_map["TEST_SESSION"] = "FAILED"
            elif skipped > 0 and passed == 0:
                status_map["TEST_SESSION"] = "SKIPPED"
            elif passed > 0:
                status_map["TEST_SESSION"] = "PASSED"
            else:
                status_map["TEST_SESSION"] = "UNKNOWN"
            continue
            
        if "FAILURES" in line or "ERRORS" in line:
            status_map["HAS_FAILURES"] = "TRUE"
            continue
            

        if "no tests ran" in line.lower() or "collected 0 items" in line.lower():
            status_map["NO_TESTS"] = "TRUE"
            continue

    return status_map

def parse_log_terraform(log: str) -> dict[str, str]:

    import re
    status_map = {}
    
    for line in log.splitlines():
        line = line.strip()

        ok_match = re.match(r"^ok\s+(\S+)\s+(.*)$", line)
        if ok_match:
            package = ok_match.group(1)
            status_map[package] = "PASSED"
            continue

        fail_match = re.match(r"^FAIL\s+(\S+)\s+(.*)$", line)
        if fail_match:
            package = fail_match.group(1)
            if "build failed" in fail_match.group(2):
                status_map[package] = "ERROR"
            else:
                status_map[package] = "FAILED"
            continue

        no_test_match = re.match(r"^\?\s+(\S+)\s+\[no test files\]$", line)
        if no_test_match:
            package = no_test_match.group(1)
            status_map[package] = "SKIPPED"
            continue

        if "COMPILATION ERROR" in line:
            status_map["COMPILATION_ERROR"] = "ERROR"
            continue

        if "Failed to execute goal" in line and "[ERROR]" in line:
            status_map["BUILD_ERROR"] = "ERROR"
            continue

    return status_map

def parse_log_polaris(log: str) -> dict[str, str]:

    status_map = {}

    status_normalization_map = {
        'PASS': 'PASSED',
        'FAIL': 'FAILED',
    }

    log_pattern = re.compile(r":test:\s+(PASS|FAIL)\s+([\S]+\.test\.(?:ts|js|tsx))")

    for line in log.splitlines():
        match = log_pattern.search(line)
        if match:
            indicator = match.group(1)
            test_path = match.group(2)

            normalized_status = status_normalization_map.get(indicator)

            if not normalized_status:
                continue

            if status_map.get(test_path) == 'FAILED':
                continue
            
            status_map[test_path] = normalized_status
            
    return status_map

def parse_log(log: str) -> dict[str, str]:
    status_map = {}

    status_normalization_map = {
        '✓': 'PASSED',
        '✗': 'FAILED',
    }

    case_pattern = re.compile(r"^(?:\s*)?(✓|✗)\s+(.+?)\s*$")
    stderr_pattern = re.compile(r"^stderr\s*\|\s*(.+?)(?:\s*$)")

    all_cases = []
    stderr_errors = []

    for line in log.splitlines():
        m_case = case_pattern.match(line)
        if m_case:
            indicator, case_name = m_case.groups()
            normalized_status = status_normalization_map.get(indicator)
            if normalized_status:
                if status_map.get(case_name) != 'FAILED':
                    status_map[case_name] = normalized_status
                all_cases.append(case_name)
            continue

        m_err = stderr_pattern.match(line)
        if m_err:
            stderr_errors.append(m_err.group(1).strip())

    # 处理stderr中的错误
    for err_case in stderr_errors:
        # 如果stderr行完全匹配到某个case，直接标记失败
        if err_case in status_map:
            status_map[err_case] = 'FAILED'
        else:
            # 部分匹配：例如 "packages/components/form/__tests__/form.test.tsx > Form"
            for case_name in all_cases:
                if case_name.startswith(err_case + " >"):
                    status_map[case_name] = 'FAILED'

    return status_map

def parse_log_cosmos_sdk(log_text: str) -> dict[str, str]:

    status_map = {}
    
    if not log_text or not log_text.strip():
        print("[WARN] parse_log received empty log")
        status_map["EMPTY_LOG"] = "ERROR"
        return status_map
    
    print("[INFO] Parsing Go test format")
    lines = log_text.splitlines()
    
    current_package = ""
    running_tests = set()
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        match = re.match(r'^===\s+RUN\s+([\w/]+)', line_stripped)
        if match:
            test_name = match.group(1)
            running_tests.add(test_name)
            continue

        match = re.match(r'^---\s+(PASS|FAIL|SKIP):\s+([\w/]+)\s+\(([0-9.]+s)\)', line_stripped)
        if match:
            status = match.group(1).upper()
            test_name = match.group(2)
            duration = match.group(3)

            status_map[test_name] = status

            if test_name in running_tests:
                running_tests.remove(test_name)

            status_map[f"{test_name}__DURATION"] = duration
            continue

        if line_stripped == "PASS":
            continue

        match = re.match(r'^(ok|FAIL)\s+([\w/.\-]+)\s+([0-9.]+s)(?:\s+coverage:\s+([0-9.]+)%)?', line_stripped)
        if match:
            pkg_status = match.group(1).upper()
            package_name = match.group(2)
            duration = match.group(3)
            coverage = match.group(4) if match.group(4) else None
            
            current_package = package_name

            if pkg_status == "OK":
                status_map[f"PKG__{package_name}"] = "PASSED"
            else:
                status_map[f"PKG__{package_name}"] = "FAILED"
            
            status_map[f"PKG__{package_name}__DURATION"] = duration
            if coverage:
                status_map[f"PKG__{package_name}__COVERAGE"] = coverage
            continue

        if re.search(r'panic.*timed?\s*out', line_stripped, re.IGNORECASE):
            status_map["TEST_TIMEOUT"] = "ERROR"
            continue

        if re.search(r'\[build failed\]', line_stripped, re.IGNORECASE):
            status_map["BUILD_ERROR"] = "ERROR"
            if current_package:
                status_map[f"PKG__{current_package}"] = "BUILD_FAILED"
            continue

        if line_stripped.startswith("go:") and ("error" in line_stripped.lower() or "requires" in line_stripped.lower()):
            status_map["GO_ERROR"] = "ERROR"
            status_map["GO_ERROR_MSG"] = line_stripped
            continue

        if "DATA RACE" in line_stripped:
            status_map["RACE_DETECTED"] = "WARNING"
            continue

        if re.search(r'make.*:\s*\*\*\*.*error', line_stripped, re.IGNORECASE):
            status_map["MAKE_ERROR"] = "ERROR"
            continue

    for test in running_tests:
        if test not in status_map:
            status_map[test] = "INCOMPLETE"
    
    all_tests = {k: v for k, v in status_map.items() 
                 if not k.startswith("PKG__") and not k.endswith("__DURATION") and not k.endswith("__COVERAGE")
                 and v in ("PASS", "FAIL", "SKIP", "INCOMPLETE")}
    
    passed_count = sum(1 for v in all_tests.values() if v == "PASS")
    failed_count = sum(1 for v in all_tests.values() if v == "FAIL")
    skipped_count = sum(1 for v in all_tests.values() if v == "SKIP")
    incomplete_count = sum(1 for v in all_tests.values() if v == "INCOMPLETE")
    
    status_map["TESTS_PASSED"] = str(passed_count)
    status_map["TESTS_FAILED"] = str(failed_count)
    status_map["TESTS_SKIPPED"] = str(skipped_count)
    if incomplete_count > 0:
        status_map["TESTS_INCOMPLETE"] = str(incomplete_count)
    status_map["TESTS_TOTAL"] = str(passed_count + failed_count + skipped_count + incomplete_count)
    
    # ========== 判断总体测试状态 ==========
    if failed_count > 0 or incomplete_count > 0:
        status_map["TEST_SUMMARY"] = "FAILED"
    elif passed_count > 0:
        status_map["TEST_SUMMARY"] = "PASSED"
    elif "BUILD_ERROR" in status_map or "GO_ERROR" in status_map or "MAKE_ERROR" in status_map:
        status_map["TEST_SUMMARY"] = "ERROR"
    elif skipped_count > 0 and passed_count == 0 and failed_count == 0:
        status_map["TEST_SUMMARY"] = "SKIPPED"
    else:
        status_map["TEST_SUMMARY"] = "UNKNOWN"

    if not all_tests and not any(k.startswith("PKG__") for k in status_map.keys()):
        print("[WARN] No test results parsed from log")
        status_map["NO_RESULTS_PARSED"] = "UNKNOWN"
    
    return status_map

def parse_log_element_plus(log: str) -> dict[str, str]:
    status_map = {}

    status_normalization_map = {
        '✓': 'PASSED',
        '✗': 'FAILED',
    }

    case_pattern = re.compile(r"^(?:\s*)?(✓|✗)\s+(.+?)\s*$")
    stderr_pattern = re.compile(r"^stderr\s*\|\s*(.+?)(?:\s*$)")

    all_cases = []
    stderr_errors = []

    for line in log.splitlines():
        m_case = case_pattern.match(line)
        if m_case:
            indicator, case_name = m_case.groups()
            normalized_status = status_normalization_map.get(indicator)
            if normalized_status:
                if status_map.get(case_name) != 'FAILED':
                    status_map[case_name] = normalized_status
                all_cases.append(case_name)
            continue

        m_err = stderr_pattern.match(line)
        if m_err:
            stderr_errors.append(m_err.group(1).strip())

    for err_case in stderr_errors:

        if err_case in status_map:
            status_map[err_case] = 'FAILED'
        else:
            for case_name in all_cases:
                if case_name.startswith(err_case + " >"):
                    status_map[case_name] = 'FAILED'

    return status_map
    
def parse_log_micropython(log_text: str) -> dict[str, str]:

    status_map = {}
    
    if not log_text or not log_text.strip():
        print("[WARN] parse_log received empty log")
        status_map["EMPTY_LOG"] = "ERROR"
        return status_map
    
    print("[INFO] Parsing MicroPython test format")
    lines = log_text.splitlines()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        match = re.match(r'^(pass|skip|fail)\s+([\w/._\-]+\.py)\s*', line, re.IGNORECASE)
        if match:
            status = match.group(1).upper()
            test_file = match.group(2)
            status_map[test_file] = status
            continue

        match = re.match(r'^(\d+)\s+tests?\s+performed(?:\s+\((\d+)\s+individual\s+testcases\))?', line)
        if match:
            status_map["TESTS_PERFORMED"] = match.group(1)
            if match.group(2):
                status_map["INDIVIDUAL_TESTCASES"] = match.group(2)
            continue

        match = re.match(r'^(\d+)\s+tests?\s+passed', line)
        if match:
            status_map["TESTS_PASSED"] = match.group(1)
            continue

        match = re.match(r'^(\d+)\s+tests?\s+failed:\s*(.+)', line)
        if match:
            status_map["TESTS_FAILED"] = match.group(1)

            continue
       
        match = re.match(r'^(\d+)\s+tests?\s+skipped:\s*(.+)', line)
        if match:
            status_map["TESTS_SKIPPED"] = match.group(1)
          
            continue

        if re.search(r'make.*:\s*\*\*\*.*error', line, re.IGNORECASE):
            status_map["MAKE_ERROR"] = "ERROR"
            continue

        if re.search(r'(compilation|build)\s+(error|failed)', line, re.IGNORECASE):
            status_map["BUILD_ERROR"] = "ERROR"
            continue

    tests_failed = int(status_map.get("TESTS_FAILED", "0"))
    tests_passed = int(status_map.get("TESTS_PASSED", "0"))
    
    if tests_failed > 0:
        status_map["TEST_SUMMARY"] = "FAILED"
    elif tests_passed > 0:
        status_map["TEST_SUMMARY"] = "PASSED"

    if not status_map or all(k.endswith("_ERROR") for k in status_map.keys()):
        print("[WARN] No test results parsed from log")
        status_map["NO_RESULTS_PARSED"] = "UNKNOWN"
    
    return status_map

def get_parse_log(repo_key: str):

    normalized = repo_key.replace("-", "_")
    func_name = f"parse_log_{normalized}"
    print(func_name)
    func = globals().get(func_name)
    if callable(func):
        return func
    print("Parse Not Found!")
    return None
