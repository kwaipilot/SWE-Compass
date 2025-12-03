import os
import random
import subprocess
import re
import json
from typing import Dict, List, Tuple, Optional
from bs4 import BeautifulSoup

from collections import defaultdict
from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

# ======================
# CONSTANTS
# ======================
TEST_CMDS = {
    "sveltejs/svelte": {
        "pre_test_cmd": "cd /testbed && pnpm install && pnpm add -D -w c8",
        "test_cmd": "npx c8 --reporter=text --reporter=html --reporter=json --reports-dir=/tmp/coverage npx vitest run --reporter=verbose <specific-test-file>"
    },
    "sympy/sympy": {
        "pre_test_cmd": "cd /testbed && pip install -e . && pip install setuptools coverage pytest pytest-cov hypothesis",
        "test_cmd": "cd /testbed && pytest <specific-test-file> --cov=. --cov-branch --cov-report=term-missing --cov-report=xml:/tmp/coverage/coverage.xml --cov-report=html:/tmp/coverage --cov-report=json:/tmp/coverage/coverage.json"
    },
    "keras-team/keras": {
        "pre_test_cmd": "cd /testbed && pip install setuptools pytest pytest-cov coverage",
        "test_cmd": "cd /testbed && pytest <specific-test-file> -v --cov=keras --cov-branch --cov-report=term --cov-report=xml:/tmp/coverage/coverage.xml --cov-report=html:/tmp/coverage --cov-report=json:/tmp/coverage/coverage.json"
    },
    "eslint/eslint": {
        "pre_test_cmd": "cd /testbed && npm install --legacy-peer-deps && npm install --save-dev c8",
        "test_cmd": "npx c8 --reporter=text --reporter=html --reporter=json --reports-dir=/tmp/coverage ./node_modules/.bin/mocha --reporter spec <specific-test-file>"
    },
    "python/mypy": {
        "pre_test_cmd": "cd /testbed && pip install -e . && pip install setuptools coverage pytest pytest-cov",
        "test_cmd": "cd /testbed && pytest -k <specific-test-file> -v -n0 --cov=mypy --cov-branch --cov-report=term-missing --cov-report=xml:/tmp/coverage/coverage.xml --cov-report=html:/tmp/coverage --cov-report=json:/tmp/coverage/coverage.json"
    },
    "jhipster/generator-jhipster": {
        "pre_test_cmd": "cd /testbed && npm ci && npm link && npm install --save-dev c8",
        "test_cmd": "cd /testbed && npx c8 --reporter=text --reporter=html --reporter=json --reports-dir=/tmp/coverage npm test -- <specific-test-file>"
    },
    "webpack/webpack": {
        "pre_test_cmd": "cd /testbed && yarn install && yarn setup && yarn add -D c8",
        "test_cmd": "cd /testbed && npx c8 --reporter=text --reporter=html --reporter=json --reports-dir=/tmp/coverage yarn test -- --testPathPattern=<specific-test-file>"
    },
    "prisma/prisma": {
        "pre_test_cmd": "cd /testbed && npm install -g pnpm && pnpm install && pnpm build && pnpm add -D -w c8",
        "test_cmd": "cd /testbed && GITHUB_REF_NAME=develop npx c8 --reporter=text --reporter=html --reporter=json --reports-dir=/tmp/coverage pnpm test <specific-test-file>"
    },
    "simple-icons/simple-icons": {
        "pre_test_cmd": "cd /testbed && npm install --no-audit --no-fund && npm install --save-dev c8",
        "test_cmd": "cd /testbed && npx c8 --reporter=text --reporter=html --reporter=json --reports-dir=/tmp/coverage npm test -- <specific-test-file>"
    }
}


# ======================
# UTILS
# ======================
def execute_cmd(cmd):
    # Execute a single command
    try:
        print(cmd, flush=True)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {
            'cmd': ' '.join(cmd),
            'returncode': result.returncode,
            'success': result.returncode == 0
        }
    except Exception as e:
        print(f"Error execute {e}: {cmd}", flush=True)
        return {
            'cmd': ' '.join(cmd),
            'error': str(e),
            'success': False
        }
    
def _get_common_parent_directory(file_paths):
    # Extract the common parent directory for multiple file paths
    if not file_paths:
        return None
    
    if len(file_paths) == 1:
        if "/" not in file_paths[0]:
            return ""
        
        return "/".join(file_paths[0].split("/")[:-1])
    
    split_paths = [path.split("/") for path in file_paths]
    
    min_length = min(len(p) for p in split_paths)
    
    common_parts = []
    for i in range(min_length):
        if len(set(p[i] for p in split_paths)) == 1:
            common_parts.append(split_paths[0][i])
        else:
            break
    
    if common_parts:
        last_part = common_parts[-1]
        if '.' in last_part:
            common_parts = common_parts[:-1]
    
    return "/".join(common_parts) if common_parts else None

def generate_eval_script(
    repo,
    base_commit,
    model_patch,
    instance_log_dir
):
    parse_error = False

    script_cmds = []

    # Step 1: Checkout branch
    script_cmds.append(
        f"cd /testbed && git checkout {base_commit}"
    )

    # Step 2: Apply patches
    script_cmds.append(
        "cd /testbed && git apply -v /tmp/code.patch"
    )

    script_cmds.append(
        f"cd /testbed && git apply -v /tmp/test.patch"
    )

    # Step 3: Run pre-test command
    pre_test_cmd = TEST_CMDS[repo]['pre_test_cmd']
    script_cmds.append(
        f"cd /testbed && {pre_test_cmd}"
    )

    model_patch_content = model_patch
    test_patch_content = ""
    # Extract test files present in the test patch
    test_file_names = []
    try:
        for chunk in PatchSet(model_patch_content):
            chunk_file_path = str(chunk.path)
            chunk_file_name = chunk_file_path.split("/")[-1]
            if chunk_file_name == "__init__.py":
                continue

            if chunk_file_name.endswith(".js") or chunk_file_name.endswith(".ts") or chunk_file_name.endswith(".py") or chunk_file_name.endswith(".test"):
                    if any(test_word in chunk.path.lower() for test_word in ["test", "tests", "e2e", "testing"]):
                        test_patch_content += str(chunk)
                        if chunk_file_path not in test_file_names:
                            test_file_names.append(chunk_file_path)
    except UnidiffParseError as e:
        parse_error = True

    if len(test_file_names) > 0:
        test_patch_file = os.path.join(instance_log_dir, "test.patch")
        with open(test_patch_file, "w") as f:
            f.write(test_patch_content)

        if repo == "python/mypy":
            # Remove suffixes for mypy
            new_test_file_names = []
            for test_file_name in test_file_names:
                test_file_name = test_file_name.split("/")[-1]
                if test_file_name.endswith(".test"):
                    test_file_name = test_file_name.replace(".test", "")
                
                new_test_file_names.append(test_file_name)
            
            test_file_names = new_test_file_names
        elif repo == "webpack/webpack":
            # Webpack: Extract common parent directory
            common_dir = _get_common_parent_directory(test_file_names)
            if common_dir:
                if common_dir.startswith("test/"):
                    common_dir = common_dir.split("test/", 1)[1]
                test_file_names = [common_dir]

        test_cmd = TEST_CMDS[repo]['test_cmd'].replace("<specific-test-file>", " ".join(test_file_names))
        script_cmds.append(
            f"cd /testbed && {test_cmd}"
        )
    else:
        parse_error = True

    if parse_error:
        return []
    
    return script_cmds

def generate_docker_run_cmd(
    instance_log_dir,
    container_name,
    docker_image_name
):
    host_uid = os.getuid()
    host_gid = os.getgid()

    docker_run_cmd = [
        "docker", "run", "--rm",
        "--privileged",
        "-e", f"HOST_UID={host_uid}",
        "-e", f"HOST_GID={host_gid}",
        "--mount", f"type=bind,source={instance_log_dir},target=/tmp",
        "--name", container_name,
        docker_image_name,
        "/bin/bash", "-c",
        "cp /tmp/eval.sh /testbed && bash /testbed/eval.sh 2>&1 | tee /tmp/eval.log; chown -R $HOST_UID:$HOST_GID /tmp"
    ]

    return docker_run_cmd

# ======================
# ANALYSIS COVERAGE
# ======================
def _is_supported_file(file_path: str) -> bool:
    # Check if file type is supported
    return file_path.endswith(('.py', '.ts', '.js'))


def _extract_patch_lines(patch_content: str) -> Dict[str, List[int]]:
    # Extract files and line numbers from patch content
    related_lines = defaultdict(list)
    
    try:
        for patched_file in PatchSet(patch_content):
            file_path = patched_file.path
            
            if file_path.startswith(('a/', 'b/')):
                file_path = file_path[2:]
            
            for chunk in patched_file:
                for line in chunk:
                    if line.is_added or line.is_context:
                        if line.target_line_no is not None:
                            related_lines[file_path].append(line.target_line_no)
    except Exception as e:
        print(f"Failed to parse patch: {e}")
    
    return related_lines


def _analyze_file_coverage(
    coverage_dir: str, 
    file_path: str, 
    lines: List[int]
) -> Optional[Dict]:
    # Analyze coverage for a single file
    
    html_path = _find_coverage_html(coverage_dir, file_path)
    if not html_path:
        return None
    
    if file_path.endswith('.py'):
        line_coverage, branch_coverage = _parse_pytest_cov_html(html_path)
    elif file_path.endswith(('.ts', '.js')):
        line_coverage, branch_coverage = _parse_c8_coverage_html(html_path)
    else:
        return None
    
    unique_lines = sorted(set(lines))
    line_cov_data = _analyze_line_coverage(line_coverage, unique_lines)
    branch_cov_data = _analyze_branch_coverage(branch_coverage, unique_lines)
    
    uncovered_lines = [
        ln for ln, is_covered in line_cov_data['line_details'].items()
        if not is_covered['covered']
    ]
    
    partial_branches = {
        ln: info for ln, info in branch_cov_data['branch_details'].items()
        if info['covered'] < info['total']
    }
    
    return {
        'line_coverage': {
            'covered': line_cov_data['covered_lines'],
            'total': line_cov_data['total_lines'],
            'percentage': line_cov_data['coverage_percentage']
        },
        'branch_coverage': {
            'covered': branch_cov_data['covered_branches'],
            'total': branch_cov_data['total_branches'],
            'percentage': branch_cov_data['coverage_percentage']
        },
        'uncovered_lines': uncovered_lines,
        'partial_branches': partial_branches
    }


def _find_coverage_html(coverage_dir: str, source_file: str) -> Optional[str]:
    # Find the corresponding coverage HTML file
    html_file = os.path.join(coverage_dir, source_file + '.html')
    if os.path.exists(html_file):
        return html_file
    
    base_name = source_file.replace('/', '_').replace('.py', '_py').replace('.ts', '_ts').replace('.js', '_js')
    patterns = [
        f"{base_name}.html",
        f"z_{base_name}.html",
    ]
    
    for pattern in patterns:
        html_file = os.path.join(coverage_dir, pattern)
        if os.path.exists(html_file):
            return html_file
    
    basename_only = os.path.basename(source_file).rsplit('.', 1)[0]
    for root, dirs, files in os.walk(coverage_dir):
        for file in files:
            if file.endswith('.html') and basename_only in file:
                return os.path.join(root, file)
    
    return None


def _parse_c8_coverage_html(html_path: str) -> Tuple[Dict[int, bool], Dict[int, Dict]]:
    # Parse c8 (JS/TS) HTML coverage report
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    line_coverage = {}
    branch_coverage = {}
    
    table = soup.find('table', class_='coverage')
    if not table:
        return line_coverage, branch_coverage
    
    rows = table.find_all('tr')
    
    for tr in rows:
        tds = tr.find_all('td')
        
        if len(tds) < 2:
            continue
        
        line_count_td = tds[0]
        line_coverage_td = tds[1]
        
        line_numbers = []
        for a in line_count_td.find_all('a', href=True):
            href = a.get('href', '')
            match = re.search(r'#L(\d+)', href)
            if match:
                line_numbers.append(int(match.group(1)))
        
        coverage_spans = line_coverage_td.find_all('span', class_=re.compile(r'cline-'))
        
        for i, line_no in enumerate(line_numbers):
            if i < len(coverage_spans):
                span = coverage_spans[i]
                classes = span.get('class', [])
                
                if 'cline-yes' in classes:
                    line_coverage[line_no] = True
                elif 'cline-no' in classes:
                    line_coverage[line_no] = False
    
    return line_coverage, branch_coverage


def _parse_pytest_cov_html(html_path: str) -> Tuple[Dict[int, bool], Dict[int, Dict]]:
    # Parse pytest-cov HTML coverage report
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    line_coverage = {}
    branch_coverage = {}
    
    main = soup.find('main', id='source')
    if not main:
        return line_coverage, branch_coverage
    
    paragraphs = main.find_all('p')
    
    for p in paragraphs:
        classes = p.get('class', [])
        
        if 'pln' in classes:
            continue
        
        n_span = p.find('span', class_='n')
        if not n_span:
            continue
        
        a_tag = n_span.find('a', id=re.compile(r'^t\d+$'))
        if not a_tag:
            continue
        
        line_id = a_tag.get('id', '')
        match = re.search(r't(\d+)', line_id)
        if not match:
            continue
        
        line_no = int(match.group(1))
        
        is_run = 'run' in classes
        is_missed = 'mis' in classes
        is_partial = 'par' in classes
        
        if is_run or is_missed or is_partial:
            line_coverage[line_no] = is_run or is_partial
        
        if is_partial:
            r_span = p.find('span', class_='r')
            if r_span:
                annotate_span = r_span.find('span', class_='annotate')
                if annotate_span:
                    title = annotate_span.get('title', '')
                    text = annotate_span.get_text(strip=True)
                    branch_info = _parse_branch_info_pytest(text, title)
                    if branch_info:
                        branch_coverage[line_no] = branch_info
    
    return line_coverage, branch_coverage


def _parse_branch_info_pytest(text: str, title: str) -> Optional[Dict]:
    # Parse pytest-cov branch coverage info
    if 'didn\'t jump' in title or 'was never' in title or 'was always' in title:
        return {
            'total': 2,
            'covered': 1,
            'percentage': 50.0,
            'annotation': title
        }
    return None


def _analyze_line_coverage(
    line_coverage: Dict[int, bool], 
    lines_to_check: List[int]
) -> Dict:
    # Analyze line coverage statistics
    covered_lines = 0
    total_lines = 0
    line_details = {}
    
    for line_no in lines_to_check:
        if line_no in line_coverage:
            total_lines += 1
            is_covered = line_coverage[line_no]
            if is_covered:
                covered_lines += 1
            
            line_details[line_no] = {
                "covered": is_covered,
                "line_number": line_no
            }
    
    coverage_percentage = (covered_lines / total_lines * 100) if total_lines > 0 else 0
    
    return {
        "covered_lines": covered_lines,
        "total_lines": total_lines,
        "coverage_percentage": round(coverage_percentage, 2),
        "line_details": line_details
    }


def _analyze_branch_coverage(
    branch_coverage: Dict[int, Dict], 
    lines_to_check: List[int]
) -> Dict:
    # Analyze branch coverage statistics
    total_branches = 0
    covered_branches = 0
    branch_details = {}
    
    for line_no in lines_to_check:
        if line_no in branch_coverage:
            branch_info = branch_coverage[line_no]
            total_branches += branch_info['total']
            covered_branches += branch_info['covered']
            branch_details[line_no] = branch_info
    
    coverage_percentage = (covered_branches / total_branches * 100) if total_branches > 0 else 0
    
    return {
        "covered_branches": covered_branches,
        "total_branches": total_branches,
        "coverage_percentage": round(coverage_percentage, 2),
        "branch_details": branch_details
    }


def calculate_patch_coverage(instance_log_dir: str) -> Dict:
    """
    Calculate coverage of the patch files.
    Supports Python (pytest-cov) and JavaScript/TypeScript (c8).
    
    Args:
        instance_log_dir: Directory containing evaluation logs.
        
    Returns:
        Dict: Coverage statistics including overall and file-specific data.
    """
    coverage_dir = os.path.join(instance_log_dir, "coverage")
    code_patch_file = os.path.join(instance_log_dir, "code.patch")
    
    result = {
        'overall': {
            'line_coverage': {'covered': 0, 'total': 0, 'percentage': 0.0},
            'branch_coverage': {'covered': 0, 'total': 0, 'percentage': 0.0}
        },
        'files': {}
    }
    
    if not os.path.exists(code_patch_file):
        result['error'] = f"Patch file not found: {code_patch_file}"
        return result
    
    if not os.path.exists(coverage_dir):
        result['error'] = f"Coverage directory not found: {coverage_dir}"
        return result
    
    try:
        with open(code_patch_file, 'r', encoding='utf-8') as f:
            patch_content = f.read()
    except Exception as e:
        result['error'] = f"Failed to read patch file: {str(e)}"
        return result
    
    related_lines_in_patch = _extract_patch_lines(patch_content)
    
    if not related_lines_in_patch:
        result['error'] = "No related files found in patch"
        return result
    
    for file_path, lines in related_lines_in_patch.items():
        if file_path.startswith('docs/') or file_path.endswith('.md'):
            continue
        
        if not _is_supported_file(file_path):
            continue
        
        file_result = _analyze_file_coverage(
            coverage_dir, file_path, lines
        )
        
        if file_result:
            result['files'][file_path] = file_result
            
            result['overall']['line_coverage']['covered'] += file_result['line_coverage']['covered']
            result['overall']['line_coverage']['total'] += file_result['line_coverage']['total']
            result['overall']['branch_coverage']['covered'] += file_result['branch_coverage']['covered']
            result['overall']['branch_coverage']['total'] += file_result['branch_coverage']['total']
    
    if result['overall']['line_coverage']['total'] > 0:
        result['overall']['line_coverage']['percentage'] = round(
            result['overall']['line_coverage']['covered'] / 
            result['overall']['line_coverage']['total'] * 100, 2
        )
    
    if result['overall']['branch_coverage']['total'] > 0:
        result['overall']['branch_coverage']['percentage'] = round(
            result['overall']['branch_coverage']['covered'] / 
            result['overall']['branch_coverage']['total'] * 100, 2
        )
    
    return result


def get_coverage_percentage(instance_log_dir):
    percentage = 0
    try:
        result = calculate_patch_coverage(instance_log_dir)
        patch_coverage_result_file = os.path.join(instance_log_dir, "patch_coverage_result.json")
        with open(patch_coverage_result_file, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        result_overall = result["overall"]
        percentage = result_overall["line_coverage"]["percentage"] / 100
    except Exception as e:
        print(f"Error calculating coverage: {e}")

    return percentage

# ======================
# API
# ======================
def run_unit_generation(
    instance_id,
    repo,
    repo_key,
    base_commit,
    model_patch,
    code_patch,
    log_dir
):
    random_number_1 = random.randint(1000000, 9999999)
    random_number_2 = random.randint(1000000, 9999999)
    container_name = f"swe_compass_eval_ut_{instance_id}_{random_number_1}_{random_number_2}"
    docker_image_name = f"swecompass/eval:{repo_key}"

    instance_log_dir = os.path.join(log_dir, instance_id)
    os.makedirs(instance_log_dir, exist_ok=True)

    original_mode = os.stat(instance_log_dir).st_mode
    try:
        eval_script_cmds = generate_eval_script(
            repo=repo,
            base_commit=base_commit,
            model_patch=model_patch,
            instance_log_dir=instance_log_dir
        )
        if len(eval_script_cmds) == 0:
            print(f"generate_eval_script failed for {instance_id}")
            return 0.0
        
        eval_script_file = os.path.join(instance_log_dir, "eval.sh")
        with open(eval_script_file, "w") as f:
            for cmd in eval_script_cmds:
                f.write(cmd + "\n")

        code_patch_file = os.path.join(instance_log_dir, "code.patch")
        with open(code_patch_file, "w") as f:
            f.write(code_patch)

        cmd = generate_docker_run_cmd(
            instance_log_dir=instance_log_dir,
            container_name=container_name,
            docker_image_name=docker_image_name
        )

        result = execute_cmd(cmd)

        eval_score = get_coverage_percentage(
            instance_log_dir=instance_log_dir
        )
            

        if result['success']:
            return eval_score
    except Exception as e:
        print(f"Error in run_coverage_generate for {instance_id}: {e}", flush=True)
    finally:
        pass

    return 0.0

def evaluate(data: Dict, log_dir: str) -> float:
    """
    Evaluate code understanding for a single instance.
    
    Args:
        data: JSON data dict containing:
            - instance_id: str
            - model_patch: str (model's answer)
            - test_patch: str (optional, PR context)
        log_dir: Directory for log files.

    Returns:
        float: Average score (0.0-1.0)
    """

    instance_id = data["instance_id"]
    repo = data["repo"]
    base_commit = data["base_commit"]
    model_patch = data["model_patch"]
    repo_key = data["repo_key"]
    test_patch = data["test_patch"]

    score = run_unit_generation(
        instance_id=instance_id,
        repo=repo,
        repo_key=repo_key,
        base_commit=base_commit,
        model_patch=model_patch,
        code_patch=test_patch,
        log_dir=log_dir
    )
    
    return score