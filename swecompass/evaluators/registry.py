import logging
from dataclasses import asdict
from swecompass.evaluators.tasks import (
    eval_performance_optimization,
    eval_selected, 
    eval_code_understanding,
    eval_unit_test_generation,
    eval_configuration_deployment
)

logger = logging.getLogger(__name__)

class EvaluatorDispatcher:

    @staticmethod
    def dispatch(item: dict, context):

        source = item.get("source", "").lower()
        try:            
            if source == "performance_optimization":
                eval_performance_optimization(data=item, work_root=str(context.work_dir) + "/performance_optimization", tmp_dir=str(context.tmp_dir), proxy=context.proxy)
            
            elif source == "selected":
                eval_selected(data=item, work_root=str(context.work_dir) + "/selected", tmp_dir=str(context.tmp_dir), proxy=context.proxy)
            
            elif source == "code_understanding":
                eval_code_understanding(data=item, log_dir=str(context.work_dir) + "/code_understanding" , model_name=context.model_name, api_key=context.api_key, base_url=context.base_url)

            elif source == "test_case_generation":
                eval_unit_test_generation(data=item, log_dir=str(context.work_dir) + "/test_case_generation")

            elif source == "configuration_deployment":
                eval_configuration_deployment(data=item, work_root=str(context.work_dir) + "/configuration_deployment", tmp_dir=str(context.tmp_dir), proxy=context.proxy)

            else:
                logger.warning(f"No specific evaluator for source: {source}, skipping.")

        except Exception as e:
            logger.error(f"Error in evaluator for item {item.get('id')}: {e}")
            raise e