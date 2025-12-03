import concurrent.futures
import logging
from tqdm import tqdm
from swecompass.evaluators.registry import EvaluatorDispatcher

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def __init__(self, context):
        self.context = context

    def run(self, dataset: list):
        logger.info(f"Starting evaluation with {self.context.max_workers} workers...")

        # run tasks using multi-process execution
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.context.max_workers) as executor:
            # submit each evaluation task to the process pool
            future_to_item = {
                executor.submit(EvaluatorDispatcher.dispatch, item, self.context): item 
                for item in dataset
            }
            
            # display progress bar for task completion
            for future in tqdm(concurrent.futures.as_completed(future_to_item), total=len(dataset), desc="Evaluating"):
                item = future_to_item[future]
                try:
                    # execute task and surface exceptions if any
                    future.result()
                except Exception as exc:
                    logger.error(f"Task {item.get('id')} generated an exception: {exc}")
