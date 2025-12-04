<div align="center">
  <img src="https://cdn-uploads.huggingface.co/production/uploads/61ee40a269351366e29972ad/KIYEa1c_WJEWPpeS0L_k1.png" width="100%" alt="Kwaipilot" />
   <hr>
  <div align="center" style="line-height: 1;">
    <a href="https://huggingface.co/datasets/Kwaipilot/SWE-Compass"><img alt="Hugging Face"
      src="https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-swecompass-ffc107?color=ffc107&logoColor=white"/></a>
    <a href="https://github.com/shunxing12345/swecompass/blob/main/LICENSE"><img alt="License"
    src="https://img.shields.io/badge/License-Apache%202.0-f5de53?&color=f5de53"/></a>
    <a href="https://arxiv.org/abs/2511.05459"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2511.05459-B31B1B?logo=arxiv&logoColor=white"/></a>
    <br>
    <a href="https://github.com/kwaipilot/SWE-Compass/stargazers"><img alt="GitHub stars"
    src="https://img.shields.io/github/stars/kwaipilot/SWE-Compass"/></a>
    <a href="https://github.com/kwaipilot/SWE-Compass/network"><img alt="GitHub forks"
    src="https://img.shields.io/github/forks/kwaipilot/SWE-Compass"/></a>
    </div>
</div>

---

## 🧠 SWE-Compass: Towards Unified Evaluation of Agentic Coding Abilities for Large Language Models

Current evaluations of LLMs for software engineering are limited by a narrow range of task categories, a Python-centric bias, and insufficient alignment with real-world development workflows.  
To bridge these gaps, SWECompass establishes a **high-coverage, multi-dimensional, and production-aligned evaluation framework**:

* ✨ Covers **8 software engineering task types, 8 programming scenarios, and 10 programming languages**
* ✨ Contains **2000 high-quality instances sourced from real GitHub pull requests**
* ✨ Supports multi-dimensional performance comparison across task types, languages, and scenarios

By integrating heterogeneous code tasks with real engineering practices, SWECompass provides a **reproducible, rigorous, and production-oriented benchmark** for diagnosing and improving the software engineering capabilities of large language models.

---


## ✨ Key Features

* ⚙️ Automated Docker-based evaluation environment
* 📦 Multi-project, multi-task, multi-language
* 🤖 Supports execution and evaluation of model-generated patches
* 📊 Multi-dimensional performance metrics: task type, scenario, language
* 🌟 Optional integration with an LLM judge for code understanding tasks
* 🔄 Highly reproducible, designed for research and production applications

---

# 📦 1. Environment Setup

### 1.1 Install Docker

Refer to the official documentation:  
https://docs.docker.com/engine/install/

### 1.2 Install Python 3.11 and Dependencies

Enter the project directory and run:

```bash
cd swe-compass
pip install -e .
pip install -r requirements.txt
````

---

# 🐳 2. Download Required Docker Images and Supplementary Data

Enter the project directory and run:

```bash
cd swe-compass
bash pull_docker.sh
python download_all_data.py
```

The scripts will automatically download the evaluation environment from DockerHub.

---

# 📄 3. Prepare Prediction Data

You need to prepare a JSON file that maps each `instance_id` to its corresponding patch and metadata.

Example format (see `swe-compass/data/example.json`):

```json
{
  "<instance_id>": {
    "model_name_or_path": "<your_model_name>",
    "instance_id": "<instance_id>",
    "model_patch": "<your_model_patch>"
  }
}
```

> Each prediction entry only requires three fields:
> `model_name_or_path`, `instance_id`, `model_patch`

---

# ▶️ 4. Run Evaluation

### 4.1 Basic Command

```bash
cd swe-compass
python validation.py \
  --dataset_name ./data/swecompass_all_2000.jsonl \
  --predictions_path <your_predictions.json> \
  --max_workers <num_workers> \
  --run_id <run_id> \
  --model_name <judge_model_name> \
  --api_key <judge_api_key> \
  --base_url <judge_model_base_url> \
  --proxy <proxy address>
```

### 4.2 Example

```bash
python validation.py \
  --dataset_name ./data/swecompass_all_2000.jsonl \
  --predictions_path ./data/example.json \
  --max_workers 10 \
  --run_id test \
  --model_name deepseek_v3 \
  --api_key xxx \
  --base_url xxx \
  --proxy http ... 
```

---

# 📊 5. Evaluation Outputs

---

## 5.1 Work Logs Directory

```
swe-compass/output/work/<run_id>/
```

Contains execution traces and logs for each instance.

---

## 5.2 Evaluation Results Directory

```
swe-compass/output/result/<run_id>/
```

Contains two files:

| File             | Content                                           |
| ---------------- | ------------------------------------------------- |
| `raw_data.jsonl` | Raw evaluation results for each instance          |
| `result.json`    | Aggregated scores by task, language, and scenario |

---

# ⚙️ 6. Common Arguments

| Argument             | Description                    |
| -------------------- | ------------------------------ |
| `--dataset_name`     | Path to dataset                |
| `--predictions_path` | Model predictions JSON file    |
| `--max_workers`      | Number of worker processes     |
| `--run_id`           | Unique identifier for this run |
| `--model_name`       | Judge LLM model name           |
| `--api_key`          | Judge LLM API key              |
| `--base_url`         | Judge LLM API URL              |
| `--proxy`            | Proxy address                  |

# 🤝 7. Contributions

We welcome contributions from the research community in NLP, Machine Learning, and Software Engineering.  
Researchers are encouraged to submit issues or pull requests that extend, evaluate, or refine the benchmark.

For collaboration or inquiries, please contact:

- **Xujingxuan** — xujingxuan2002@163.com  
- **Ken Deng** — dengken@kuaishou.com  
- **Jiaheng Liu** — liujiaheng@nju.edu.cn  

We appreciate constructive engagement and look forward to further improvements driven by the community.

# 📄 8. Citation

```bibtex
@article{xu2025SWECompass,
  title={SWE-Compass: Towards Unified Evaluation of Agentic Coding Abilities for Large Language Models},
  author={Xu, Jingxuan and Deng, Ken and Li, Weihao and Yu, Songwei etc},
  journal={arXiv preprint arXiv:2511.05459},
  year={2025}
}
```
