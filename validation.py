#!/usr/bin/env python

import os
import sys
import subprocess
import argparse
import time
import json 
from swecompass.core.loader import DataLoader
from swecompass.core.summary import ResultSummarizer
import logging  

# create log directory
os.makedirs('logs', exist_ok=True)

# configure main logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout), 
        logging.FileHandler(
            os.path.join('logs', 'run.log'), 
            mode='a',  
            encoding='utf-8'
        )
    ]
)

# output root directory
RUN_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(RUN_OUTPUT_DIR, exist_ok=True)

def main():
    # create argument parser, allow unknown arguments
    parser = argparse.ArgumentParser(
        description='Unified entry script',
        allow_abbrev=False,
        add_help=False  # disable default -h/--help, let subcommands handle it
    )
    
    # raw data
    parser.add_argument("--dataset_name", required=True, help="Path to the dataset (jsonl)")
    parser.add_argument("--predictions_path", required=True, help="Path to the predictions file (json)")

    # filtering options
    parser.add_argument("--task_types", default="ALL", help="Filter by task types (e.g., 'debug,generation')")
    parser.add_argument("--programming_languages", default="ALL", help="Filter by languages (e.g., 'c,cpp,java')")
    parser.add_argument("--programming_scenarios", default="ALL", help="Filter by scenarios (e.g., 'code_understanding,code_generation')")

    # run mode
    parser.add_argument("--summary_only", action="store_true", help="Skip execution, only generate summary report based on existing results")

    parser.add_argument("--run_id", default=time.strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--model_name", default=None, help="Model name for evaluation")
    parser.add_argument("--api_key", default=None, help="API key for model authentication")
    parser.add_argument("--base_url", default=None, help="API base URL endpoint")
    parser.add_argument("--proxy", help="Proxy URL (optional, can use env var)")
    
    # parse known args and remaining args
    args, remaining_args = parser.parse_known_args()
    
    # filter data
    filtered_data = DataLoader(
        dataset_name=args.dataset_name,
        predictions_path=args.predictions_path,
        task_types=args.task_types,
        programming_languages=args.programming_languages,
        programming_scenarios=args.programming_scenarios
    )
   
    tmp_dir = os.path.join(RUN_OUTPUT_DIR, "tmp", args.run_id)
    # create directory
    os.makedirs(tmp_dir, exist_ok=True)

    work_dir = os.path.join(RUN_OUTPUT_DIR, "work", args.run_id)
    # create directory
    os.makedirs(work_dir, exist_ok=True)

    result_dir = os.path.join(RUN_OUTPUT_DIR, "results", args.run_id)
    # create directory
    os.makedirs(result_dir, exist_ok=True)

    if args.summary_only:
        logging.info("Summary only mode")
    else:
        # group instances by namespace
        source_map = {
            "swecompass": {
                "filtered_dataset": [],
                "predictions": {},
            },
            "swe-bench-live": {
                "filtered_dataset": [],
                "predictions": {},
            },
            "swe-bench-multilingual": {
                "filtered_dataset": [],
                "predictions": {},
            },
            "swe-bench-verified": {
                "filtered_dataset": [],
                "predictions": {},
            },
            "swe-Rebench": {
                "filtered_dataset": [],
                "predictions": {},
            },
        }
        # split items into namespace buckets
        for item in filtered_data:
            if item["source"] in ["swe-bench-live", "swe-bench-multilingual", "swe-bench-verified", "swe-Rebench"]:
                source_map[item["source"]]["filtered_dataset"].append(item)
                source_map[item["source"]]["predictions"][item["instance_id"]] = {
                    "instance_id": item["instance_id"],
                    "model_name_or_path": item.get("model_name_or_path", ""),
                    "model_patch": item.get("model_patch", ""),
                }
            else:
                source_map["swecompass"]["filtered_dataset"].append(item)
                source_map["swecompass"]["predictions"][item["instance_id"]] = {
                    "instance_id": item["instance_id"],
                    "model_name_or_path": item.get("model_name_or_path", ""),
                    "model_patch": item.get("model_patch", ""),
                }

        # generate data files and execution cmds for namespaces
        cmds = []
        for namespace, content in source_map.items():
            namespace_work_dir = os.path.join(work_dir, namespace)
            if content["filtered_dataset"]: 
                # save data.jsonl
                data_file = os.path.join(tmp_dir, f"data_{namespace}.jsonl")
                with open(data_file, "w", encoding="utf-8") as f:
                    for item in content["filtered_dataset"]:
                        f.write(json.dumps(item) + "\n")

                
                # save pred.json
                pred_file = os.path.join(tmp_dir, f"pred_{namespace}.json")
                with open(pred_file, "w", encoding="utf-8") as f:
                    json.dump(content["predictions"], f, indent=2, ensure_ascii=False)

                # construct commands for different namespaces
                if namespace == "swecompass":
                    cmd = [
                        sys.executable, '-m', 'swecompass.entry.main',
                        '--dataset_name', data_file,
                        '--predictions_path', pred_file,
                        '--run_id', args.run_id,
                        '--model_name',args.model_name,
                        '--api_key',args.api_key,
                        '--base_url',args.base_url,
                        '--proxy',args.proxy
                    ] + remaining_args
                elif namespace == "swe-bench-live":
                    cmd = [
                        sys.executable, '-m', 'swebench.harness.run_validation',
                        '--namespace', "starryzhang",
                        '--dataset_name', data_file,
                        '--predictions_path', pred_file,
                        '--run_id', args.run_id,
                        '--source',namespace_work_dir
                    ] + remaining_args
                elif namespace == "swe-Rebench":
                    cmd = [
                        sys.executable, '-m', 'swebench.harness.run_validation',
                        '--namespace', "swerebench",
                        '--dataset_name', data_file,
                        '--predictions_path', pred_file,
                        '--run_id', args.run_id,
                        '--source',namespace_work_dir,
                    ] + remaining_args
                else:
                    cmd = [
                        sys.executable, '-m', 'swebench.harness.run_validation',
                        '--dataset_name', data_file,
                        '--predictions_path', pred_file,
                        '--run_id', args.run_id,
                        '--source',namespace_work_dir,
                    ] + remaining_args

                cmds.append(cmd)

        # environment injection for pythonpath
        env = os.environ.copy()
        current_python_path = os.environ.get('PYTHONPATH', '')
        env['PYTHONPATH'] = f"{os.getcwd()}:{current_python_path}"

        # execute commands sequentially and remain interactive
        for cmd in cmds:
            # print command (for debugging)
            logging.info(f"[INFO] Executing: {' '.join(cmd)}")
            logging.info("-" * 80)

            try:
                result = subprocess.run(cmd, env=env)
            except KeyboardInterrupt:
                logging.info("\n[INFO] Execution interrupted by user")
                sys.exit(130)
            except Exception as e:
                logging.error(f"[ERROR] Execution failed: {e}", file=sys.stderr)
                sys.exit(1)

    # Step 4: summary
    # Regardless of execution, generate summary from on-disk results
    summarizer = ResultSummarizer(
        work_dir=work_dir,
        result_dir=result_dir
    )
    summarizer.run(filtered_data)

if __name__ == '__main__':
    main()
