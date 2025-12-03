import os
import time
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
import logging

# basic logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# runtime configuration for validation
@dataclass
class RunConfig:
    run_id: str
    work_dir: Path
    tmp_dir: Path
    result_dir: Path
    max_workers: int
    model_name: str
    api_key: str = ""
    base_url: str = ""
    proxy: str = ""

# manager for building directories and runtime config
class ConfigManager:
    def __init__(self, args):
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.output_dir = self.base_dir / "output"
        self.args = args
        
        self.default_no_proxy = (
            "localhost,127.0.0.1,localaddress,localdomain.com,"
            "internal,corp.kuaishou.com,test.gifshow.com,staging.kuaishou.com"
        )

    # build runtime config and ensure directories exist
    def initialize(self) -> RunConfig:
        if self.args.run_id:
            run_id = self.args.run_id
        else:
            run_id = time.strftime("%Y%m%d_%H%M%S")
            logger.info(f"Run ID not provided, using timestamp: {run_id}")

        work_dir = self.output_dir / "work" / run_id
        tmp_dir = self.output_dir / "tmp" / run_id
        result_dir = self.output_dir / "results" / run_id

        work_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        result_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized directories:\n  Work: {work_dir}\n  Tmp: {tmp_dir}\n  Result: {result_dir}")

        model_name = getattr(self.args, 'model_name', "unknown-model")
        
        api_key = getattr(self.args, 'api_key', None)
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY", "") or os.getenv("API_KEY", "")
            
        base_url = getattr(self.args, 'base_url', None)
        if not base_url:
            base_url = os.getenv("OPENAI_BASE_URL", "") or os.getenv("BASE_URL", "")

        proxy_cmd = self._resolve_proxy_config()

        self.save_run_snapshot(RunConfig(
            run_id=run_id,
            work_dir=work_dir,
            tmp_dir=tmp_dir,
            result_dir=result_dir,
            max_workers=self.args.max_workers,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            proxy=proxy_cmd
        ))

        return RunConfig(
            run_id=run_id,
            work_dir=work_dir,
            tmp_dir=tmp_dir,
            result_dir=result_dir,
            max_workers=self.args.max_workers,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            proxy=proxy_cmd
        )

    # resolve proxy from args or system
    def _resolve_proxy_config(self) -> str:
        arg_proxy = getattr(self.args, 'proxy', None)
        if arg_proxy:
            http_val = arg_proxy
            https_val = arg_proxy
        else:
            http_val = os.getenv("http_proxy") or os.getenv("HTTP_PROXY") or ""
            https_val = os.getenv("https_proxy") or os.getenv("HTTPS_PROXY") or ""

        if not http_val and not https_val:
            return ""

        return f"export http_proxy={http_val} https_proxy={https_val}"

    # save runtime config snapshot to disk
    def save_run_snapshot(self, config: RunConfig):
        config_dict = asdict(config)
        
        for k, v in config_dict.items():
            if isinstance(v, Path):
                config_dict[k] = str(v)
        
        snapshot = {
            "run_config": config_dict
        }

        output_path = config.work_dir / "config.json"
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=4, ensure_ascii=False)
            logger.info(f"Config snapshot saved to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save config snapshot: {e}")
