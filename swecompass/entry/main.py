import argparse
import sys
import logging
from swecompass.core.config import ConfigManager
from swecompass.core.loader import DataLoader
from swecompass.core.engine import ExecutionEngine

# global logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Main")

# parse CLI arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Custom Benchmark Runner")
    
    parser.add_argument("--dataset_name", required=True, help="Path to the dataset (jsonl)")
    parser.add_argument("--predictions_path", required=True, help="Path to the predictions file (json)")
    parser.add_argument("--max_workers", type=int, default=5, help="Concurrency level")
    
    parser.add_argument("--run_id", help="Unique identifier for this run")
    
    parser.add_argument("--model_name", help="Name of the model to evaluate (Required for code_understanding)")
    parser.add_argument("--api_key", help="API Key (optional, can use env var)")
    parser.add_argument("--base_url", help="Base URL for the API (optional, can use env var)")
    parser.add_argument("--proxy", help="Proxy URL (optional, can use env var)")
    
    parser.add_argument(
        "--programming_languages",
        type=str,
        default="ALL",
        help="Filter by programming languages (comma-separated or ALL). Example: 'Python,JavaScript'"
    )
    parser.add_argument(
        "--programming_scenarios",
        type=str,
        default="ALL",
        help="Filter by programming scenarios (comma-separated or ALL). Example: 'code_understanding,bug_fixing'"
    )
    parser.add_argument(
        "--task_types",
        type=str,
        default="ALL",
        help="Filter by task types (comma-separated or ALL). Example: 'BugFix,Feature'"
    )
    args, remaining_args = parser.parse_known_args()

    return args

# validate input business rules
def validate_requirements(args):
    scenarios = args.programming_scenarios.strip().upper()
    is_all = (scenarios == "ALL")
    has_understanding = ("CODE_UNDERSTANDING" in scenarios)

    # code_understanding requires model_name
    if (is_all or has_understanding):
        if not args.model_name:
            logger.error(
                "CRITICAL VALIDATION ERROR: \n"
                "  You selected scenarios that require a model ('ALL' or 'code_understanding').\n"
                "  Please provide --model_name <your_model_name>."
            )
            sys.exit(1)

# main workflow entry
def main():
    args = parse_args()

    # validate required settings based on scenario
    validate_requirements(args)

    try:
        # initialize environment and config
        config_mgr = ConfigManager(args)
        context = config_mgr.initialize()
        
        logger.info(f"Run Configured: Model={context.model_name}, Workers={context.max_workers}")

        # load dataset + predictions
        loader = DataLoader(
            dataset_name=args.dataset_name,
            predictions_path=args.predictions_path
        )
        
        # extract filtered dataset
        dataset = loader.load_and_filter()

        if not dataset:
            logger.warning("No data found after filtering. Exiting.")
            sys.exit(0)

        # save run config snapshot
        config_mgr.save_run_snapshot(context)
        
        # run evaluation engine
        engine = ExecutionEngine(context)
        engine.run(dataset)
    except FileExistsError as fe:
        logger.error(f"Directory Conflict: {fe}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
