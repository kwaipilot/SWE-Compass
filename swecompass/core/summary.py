import json
import logging
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class ResultSummarizer:
    def __init__(self, work_dir, result_dir):
        self.work_dir = Path(work_dir)
        self.result_dir = Path(result_dir)

    # main entry to summarize results
    def run(self, dataset: List[Dict[str, Any]]):
        logger.info("Starting result summarization...")
        
        # collect raw evaluation results with scores
        detailed_results = self._collect_and_score(dataset)
        
        # save raw jsonl output
        self._save_raw_data(detailed_results)
        
        # compute aggregated metrics and save
        self._calculate_and_save_metrics(detailed_results)

    # dispatch scoring logic based on data source category
    def _collect_and_score(self, dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_data = []

        for item in dataset:
            instance_id = str(item.get("instance_id", "unknown"))
            source = str(item.get("source", "unknown"))
            
            if source == "test_case_generation":
                score, details = self._get_score_test_case_generation(source, instance_id)
            elif source == "code_understanding":
                score, details = self._get_score_code_understanding(source, instance_id)
            elif source in ["swe-bench-live", "swe-bench-multilingual", "swe-bench-verified", "swe-Rebench"]:
                score, details = self._get_opensource(source, instance_id)
            else:
                score, details = self._get_standard_score(source, instance_id)
            
            # unified summary entry
            new_item = {
                "instance_id": instance_id,
                "repo_key": item.get("repo_key"),
                "source": source,
                "programming_languages": str(item.get("programming_languages", "unknown")),
                "programming_scenarios": str(item.get("programming_scenarios", "unknown")),
                "task_types": str(item.get("task_types", "unknown")),
                "score": score,
                "result_details": details
            }
            processed_data.append(new_item)
            
        return processed_data

    # scoring for "standard tasks"
    def _get_standard_score(self, source: str, instance_id: str) -> Tuple[float, Dict]:
        path = self.work_dir / source / instance_id / "result.json"
        
        if not path.exists():
            return 0, {"error": "File not found", "path": str(path)}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                res_json = json.load(f)
            
            p2p = res_json.get("PASS_TO_PASS_result", False)
            f2p = res_json.get("FAIL_TO_PASS_result", False)
            
            is_pass = bool(p2p) and bool(f2p)
            score = 1 if is_pass else 0
            
            return score, res_json
        except Exception as e:
            logger.error(f"Error reading standard result {path}: {e}")
            return 0, {"error": str(e)}

    # scoring for code-understanding tasks
    def _get_score_code_understanding(self, source: str, instance_id: str) -> Tuple[float, Dict]:
        path = self.work_dir / source / instance_id / f"{instance_id}.json"
        
        if not path.exists():
            return 0.0, {"error": "File not found", "path": str(path)}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                res_json = json.load(f)

            percentage = (
                res_json.get("average_score", 0.0)
            )
            
            score = float(percentage)
            return score, res_json
        except Exception as e:
            logger.error(f"Error reading coverage result {path}: {e}")
            return 0.0, {"error": str(e)}
    
    # scoring for test-case generation
    def _get_score_test_case_generation(self, source: str, instance_id: str) -> Tuple[float, Dict]:
        path = self.work_dir / source / instance_id / "patch_coverage_result.json"
        
        if not path.exists():
            return 0.0, {"error": "File not found", "path": str(path)}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                res_json = json.load(f)
            
            percentage = (
                res_json.get("overall", {})
                        .get("line_coverage", {})
                        .get("percentage", 0.0)
            )
            
            score = float(percentage) / 100.0
            return score, res_json
        except Exception as e:
            logger.error(f"Error reading coverage result {path}: {e}")
            return 0.0, {"error": str(e)}

    # scoring for opensource subset tasks
    def _get_opensource(self, source: str, instance_id: str) -> Tuple[str, Dict]:
        path = self.work_dir / source / instance_id / "report.json"
        try:
            with open(path, 'r', encoding='utf-8') as f:
                res_json = json.load(f)
            
            resolved = res_json.get(instance_id, {}).get("resolved", False)
            score = 1.0 if resolved else 0.0
            return score, res_json
        except Exception as e:
            logger.error(f"Error reading result {path}: {e}")
            return 0.0, {"error": str(e)}

    # write raw records jsonl
    def _save_raw_data(self, data: List[Dict[str, Any]]):
        output_path = self.result_dir / "raw_data.jsonl"
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            logger.info(f"Raw results saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save raw data: {e}")

    # aggregate statistics at multiple dimensions
    def _calculate_and_save_metrics(self, data: List[Dict[str, Any]]):
        aggregator = {
            "overall": {"count": 0, "sum_score": 0.0},
            "programming_languages": defaultdict(lambda: {"count": 0, "sum_score": 0.0}),
            "programming_scenarios": defaultdict(lambda: {"count": 0, "sum_score": 0.0}),
            "task_types": defaultdict(lambda: {"count": 0, "sum_score": 0.0})
        }

        # accumulate scores
        for item in data:
            score = float(item["score"])
            
            aggregator["overall"]["count"] += 1
            aggregator["overall"]["sum_score"] += score
            
            lang = item["programming_languages"]
            aggregator["programming_languages"][lang]["count"] += 1
            aggregator["programming_languages"][lang]["sum_score"] += score
            
            scen = item["programming_scenarios"]
            aggregator["programming_scenarios"][scen]["count"] += 1
            aggregator["programming_scenarios"][scen]["sum_score"] += score
            
            task = item["task_types"]
            aggregator["task_types"][task]["count"] += 1
            aggregator["task_types"][task]["sum_score"] += score

        final_report = self._format_report(aggregator)
        
        output_path = self.result_dir / "result.json"
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_report, f, indent=4, ensure_ascii=False)
            logger.info(f"Statistical report saved to {output_path}")
            
            avg = final_report.get('overall', {}).get('average_score', 0)
            logger.info(f"Summary Complete. Overall Average Score: {avg:.4f}")
            
        except Exception as e:
            logger.error(f"Failed to save metrics report: {e}")

    # format aggregated results to json structure
    def _format_report(self, aggregator):
        report = {}
        
        ov = aggregator["overall"]
        count = ov["count"]
        sum_score = ov["sum_score"]
        report["overall"] = {
            "count": count,
            "average_score": round((sum_score / count), 2) if count > 0 else 0.0,
        }
        
        for dim_key in ["programming_languages", "programming_scenarios", "task_types"]:
            report[dim_key] = {}
            for cat_key, stats in aggregator[dim_key].items():
                c = stats["count"]
                s = stats["sum_score"]
                report[dim_key][cat_key] = {
                    "count": c,
                    "average_score": round((s / c), 2) if c > 0 else 0.0
                }
                
        return report
