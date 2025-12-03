import json
from typing import List, Dict, Any
from collections import Counter
import logging

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self, dataset_name: str, predictions_path: str, programming_languages: str = "ALL", programming_scenarios: str = "ALL", task_types: str = "ALL"):
        self.dataset_name = dataset_name
        self.predictions_path = predictions_path

        # store filtering rules based on fields in dataset
        self.filters = {
            "programming_languages": self._parse_filter(programming_languages),
            "programming_scenarios": self._parse_filter(programming_scenarios),
            "task_types": self._parse_filter(task_types)
        }

        # load dataset and predictions into memory
        self.data = self.load_and_filter()

    # parse comma-separated filter values
    def _parse_filter(self, filter_str: str) -> set:
        if not filter_str or filter_str.upper() == "ALL":
            return None
        return set(x.strip() for x in filter_str.split(","))

    # verify if a single item meets filter criteria
    def _check_condition(self, item: Dict, field: str) -> bool:
        target_set = self.filters.get(field)
        if target_set is None:
            return True
        value = item.get(field)
        return str(value) in target_set

    # load dataset, merge predictions, gather statistics
    def load_and_filter(self) -> List[Dict[str, Any]]:
        data = []
        
        stats = {
            "programming_languages": Counter(),
            "programming_scenarios": Counter(),
            "task_types": Counter()
        }
        
        missing_predictions = []
        total_filtered = 0

        try:
            predictions = {}
            try:
                with open(self.predictions_path, 'r', encoding='utf-8') as f:
                    predictions = json.load(f)
                logger.info(f"Loaded {len(predictions)} predictions from {self.predictions_path}")
            except FileNotFoundError:
                logger.error(f"Predictions file not found: {self.predictions_path}")
                raise
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in predictions file: {e}")
                raise
            
            # iterate over dataset jsonl and enrich items with predictions
            with open(self.dataset_name, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    item = json.loads(line)
                    
                    if (self._check_condition(item, "programming_languages") and
                        self._check_condition(item, "programming_scenarios") and
                        self._check_condition(item, "task_types")):
                        
                        total_filtered += 1
                        instance_id = item.get("instance_id")
                        
                        # only include items with predictions
                        if instance_id and instance_id in predictions:
                            pred_data = predictions[instance_id]
                            item["model_patch"] = pred_data.get("model_patch", "")
                            if "model_name_or_path" in pred_data:
                                item["model_name_or_path"] = pred_data["model_name_or_path"]
                            
                            data.append(item)

                            # collect statistics for included items
                            lang = item.get("programming_languages", "unknown")
                            scen = item.get("programming_scenarios", "unknown")
                            task = item.get("task_types", "unknown")
                            
                            stats["programming_languages"][str(lang)] += 1
                            stats["programming_scenarios"][str(scen)] += 1
                            stats["task_types"][str(task)] += 1
                        else:
                            # track missing predictions for reporting
                            missing_predictions.append(instance_id)
            
            # log dataset statistics
            self._log_statistics(len(data), total_filtered, stats, missing_predictions)
            return data
            
        except FileNotFoundError:
            logger.error(f"Dataset file not found: {self.dataset_name}")
            raise

    # format and log summary statistics
    def _log_statistics(self, valid_count: int, total_filtered: int, 
                       stats: Dict[str, Counter], missing_predictions: List[str]):
        missing_count = len(missing_predictions)
        
        if total_filtered == 0:
            logger.warning("No data passed the filtering criteria.")
            return

        log_msg = ["\n" + "="*60]
        log_msg.append(f"DATA LOADING REPORT")
        log_msg.append("="*60)
        log_msg.append(f"Items after filter criteria: {total_filtered}")
        log_msg.append(f"  • Valid predictions (loaded): {valid_count} ({valid_count/total_filtered*100:.1f}%)")
        log_msg.append(f"  • Missing predictions (excluded): {missing_count} ({missing_count/total_filtered*100:.1f}%)")
        
        if missing_predictions:
            log_msg.append(f"\n⚠️  Excluded Instances (No Predictions):")
            preview_count = min(10, len(missing_predictions))
            log_msg.append(f"   Showing first {preview_count} of {missing_count}:")
            for idx, inst_id in enumerate(missing_predictions[:preview_count], 1):
                log_msg.append(f"     {idx}. {inst_id}")
            if len(missing_predictions) > preview_count:
                log_msg.append(f"     ... and {len(missing_predictions) - preview_count} more")
        
        if valid_count == 0:
            log_msg.append("\n❌ No valid predictions found. Cannot proceed.")
            log_msg.append("="*60 + "\n")
            logger.warning("\n".join(log_msg))
            return
        
        log_msg.append("\n" + "-"*60)
        log_msg.append("DATA BREAKDOWN (Valid Predictions Only)")
        log_msg.append("-"*60)
        
        categories = [
            ("Programming Languages", stats["programming_languages"]),
            ("Programming Scenarios", stats["programming_scenarios"]),
            ("Task Types", stats["task_types"])
        ]

        # display aggregated statistics
        for title, counter in categories:
            log_msg.append(f"\n[{title}]")
            if not counter:
                log_msg.append("  (No data)")
            else:
                for key, count in counter.most_common():
                    percentage = (count / valid_count) * 100
                    log_msg.append(f"  • {key:.<30} {count:>4} ({percentage:>5.1f}%)")
        
        log_msg.append("\n" + "="*60 + "\n")
        logger.info("\n".join(log_msg))
    
    # make the loader iterable
    def __iter__(self):
        return iter(self.data)
    
    # return number of valid items
    def __len__(self):
        return len(self.data)
