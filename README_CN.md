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

[🇺🇸 English ](README.md) [🇨🇳 简体中文](README_CN.md)

---

## 🧠 SWE-Compass：面向真实软件工程的统一智能体编码能力评测基准

当前针对软件工程的 LLM 评测存在显著局限：
任务类别单一、对 Python 过度集中、缺乏与真实开发流程的对齐程度。

为弥补这些不足，SWE-Compass 提供一个**高覆盖、多维度、接近真实生产环境的评测框架**：

* ✨ 覆盖 **8 类软件工程任务、8 个编程场景、10 种编程语言**
* ✨ 包含 **2000 条来自真实 GitHub Pull Requests 的高质量实例**
* ✨ 支持基于任务、语言、场景的多维性能对比分析

通过将异构代码任务与真实工程实践深度结合，SWE-Compass 为评估与提升大模型的软件工程能力提供了一个**可复现、严谨、且生产导向的基准体系**。

---

## ✨ 主要特性

* ⚙️ 基于 Docker 的自动化评测环境
* 📦 多项目、多任务、多语言
* 🤖 支持运行和评测模型生成补丁
* 📊 多维度性能指标：任务类型、场景、语言
* 🌟 可选集成 LLM 作为代码理解评审者
* 🔄 高可复现性，适用于科研与生产环境

---

# 📦 1. 环境配置

### 1.1 安装 Docker

官方文档：
[https://docs.docker.com/engine/install/](https://docs.docker.com/engine/install/)

### 1.2 安装 Python 3.11 与依赖

进入项目目录并执行：

```bash
cd swe-compass
pip install -e .
pip install -r requirements.txt
```

---

# 🐳 2. 下载 Docker 镜像与所需数据

进入项目目录并执行：

```bash
cd swe-compass
bash pull_docker.sh
python download_all_data.py
```

脚本将自动从 DockerHub 下载评测环境。

---

# 📄 3. 准备预测文件

需要准备一个 JSON 文件，将每个 `instance_id` 映射到对应的补丁与元数据。

示例（见 `swe-compass/data/example.json`）：

```json
{
  "<instance_id>": {
    "model_name_or_path": "<your_model_name>",
    "instance_id": "<instance_id>",
    "model_patch": "<your_model_patch>"
  }
}
```

> 每条预测只需要三个字段：
> `model_name_or_path`, `instance_id`, `model_patch`

---

# ▶️ 4. 运行评测

### 4.1 基本指令

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

### 4.2 示例

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

# 📊 5. 评测输出结果

---

## 5.1 工作日志目录

```
swe-compass/output/work/<run_id>/
```

包含每个实例的执行记录与日志。

---

## 5.2 评测结果目录

```
swe-compass/output/result/<run_id>/
```

包含两个文件：

| 文件名              | 内容说明               |
| ---------------- | ------------------ |
| `raw_data.jsonl` | 每个实例的原始评测结果        |
| `result.json`    | 按任务类型、编程语言、编程场景汇总的整体评测指标 |

---

# ⚙️ 6. 常用参数

| 参数名                  | 描述           |
| -------------------- | ------------ |
| `--dataset_name`     | 数据集路径        |
| `--predictions_path` | 模型预测 JSON 文件 |
| `--max_workers`      | 并行进程数量       |
| `--run_id`           | 本次运行的唯一标识    |
| `--model_name`       | LLM Judge 模型名称       |
| `--api_key`          | LLM Judge 模型 API key |
| `--base_url`         | LLM Judge 模型 API URL |
| `--proxy`            | 代理地址         |

---

# 🤝 7. 贡献与合作

我们欢迎来自 NLP、机器学习和软件工程领域的研究者参与贡献。
您可以通过提交 Issue 或 Pull Request 来扩展、评估或改进该基准。

如需交流或合作，请联系：

* **徐景宣** — [xujingxuan2002@163.com](mailto:xujingxuan2002@163.com)
* **邓肯** — [dengken@kuaishou.com](mailto:dengken@kuaishou.com)
* **刘佳恒** — [liujiaheng@nju.edu.cn](mailto:liujiaheng@nju.edu.cn)

感谢社区的反馈与贡献，我们期待共同推动下一代软件工程评测的发展。

---

# 📄 8. 引用

```bibtex
@article{xu2025SWECompass,
  title={SWE-Compass: Towards Unified Evaluation of Agentic Coding Abilities for Large Language Models},
  author={Xu, Jingxuan and Deng, Ken and Li, Weihao and Yu, Songwei etc},
  journal={arXiv preprint arXiv:2511.05459},
  year={2025}
}
```

---
