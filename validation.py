#!/usr/bin/env python
"""
统一入口脚本，根据 namespace 参数路由到不同的执行模块
用法: python main.py [--namespace xxx] [其他参数...]
"""

import os
import sys
import subprocess
import argparse
import time
import json 
from swecompass.core.loader import DataLoader
from swecompass.core.summary import ResultSummarizer
import logging  

os.makedirs('logs', exist_ok=True)
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

RUN_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(RUN_OUTPUT_DIR, exist_ok=True)

def main():
    # 创建参数解析器，允许未知参数
    parser = argparse.ArgumentParser(
        description='统一入口脚本',
        allow_abbrev=False,
        add_help=False  # 禁用默认的 -h/--help，让子命令处理
    )
    
    # 原始数据
    parser.add_argument("--dataset_name", required=True, help="Path to the dataset (jsonl)")
    parser.add_argument("--predictions_path", required=True, help="Path to the predictions file (json)")

    # 筛选条件
    parser.add_argument("--task_types", default="ALL", help="Filter by task types (e.g., 'debug,generation')")
    parser.add_argument("--programming_languages", default="ALL", help="Filter by languages (e.g., 'c,cpp,java')")
    parser.add_argument("--programming_scenarios", default="ALL", help="Filter by scenarios (e.g., 'code_understanding,code_generation')")

    # 运行模式
    parser.add_argument("--summary_only", action="store_true", help="Skip execution, only generate summary report based on existing results")

    parser.add_argument("--run_id", default=time.strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--model_name", default=None, help="Model name for evaluation")
    parser.add_argument("--api_key", default=None, help="API key for model authentication")
    parser.add_argument("--base_url", default=None, help="API base URL endpoint")
    parser.add_argument("--proxy", help="Proxy URL (optional, can use env var)")
    
    # 解析已知参数和剩余参数
    args, remaining_args = parser.parse_known_args()
    
    # 对数据进行筛选
    filtered_data = DataLoader(
        dataset_name=args.dataset_name,
        predictions_path=args.predictions_path,
        task_types=args.task_types,
        programming_languages=args.programming_languages,
        programming_scenarios=args.programming_scenarios
    )
   
    tmp_dir = os.path.join(RUN_OUTPUT_DIR, "tmp", args.run_id)
    # 创建目录
    os.makedirs(tmp_dir, exist_ok=True)

    work_dir = os.path.join(RUN_OUTPUT_DIR, "work", args.run_id)
    # 创建目录
    os.makedirs(work_dir, exist_ok=True)

    result_dir = os.path.join(RUN_OUTPUT_DIR, "results", args.run_id)
    # 创建目录
    os.makedirs(result_dir, exist_ok=True)

    if args.summary_only:
        logging.info("Summary only mode")
    else:
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
        # 给每个namespace创建对应的 data.jsonl 和 pred.json, 并执行
        cmds = []
        for namespace, content in source_map.items():
            namespace_work_dir = os.path.join(work_dir, namespace)
            if content["filtered_dataset"]:  # 如果该namespace有数据
                # 保存 data.jsonl
                data_file = os.path.join(tmp_dir, f"data_{namespace}.jsonl")
                with open(data_file, "w", encoding="utf-8") as f:
                    for item in content["filtered_dataset"]:
                        # f.write(f"{item}\n")
                        f.write(json.dumps(item) + "\n")  # 使用 json.dumps() 转换为 JSON 字符串

                
                # 保存 pred.json
                pred_file = os.path.join(tmp_dir, f"pred_{namespace}.json")
                with open(pred_file, "w", encoding="utf-8") as f:
                    json.dump(content["predictions"], f, indent=2, ensure_ascii=False)


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

        env = os.environ.copy()
        current_python_path = os.environ.get('PYTHONPATH', '')
        env['PYTHONPATH'] = f"{os.getcwd()}:{current_python_path}"

        # 执行命令并保持交互性
        for cmd in cmds:
            # 打印将要执行的命令（便于调试）
            logging.info(f"[INFO] Executing: {' '.join(cmd)}")
            logging.info("-" * 80)

            try:
                result = subprocess.run(cmd, env=env)
            except KeyboardInterrupt:
                logging.info("\n[INFO] 用户中断执行")
                sys.exit(130)
            except Exception as e:
                logging.error(f"[ERROR] 执行失败: {e}", file=sys.stderr)
                sys.exit(1)


    # Step 4: 汇总 (Summary)
    # 无论是否刚刚执行过，都基于磁盘上的结果文件进行汇总
    summarizer = ResultSummarizer(
        work_dir=work_dir,
        result_dir=result_dir
    )
    summarizer.run(filtered_data)

if __name__ == '__main__':
    main()
