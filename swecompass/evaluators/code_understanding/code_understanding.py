#!/usr/bin/env python3
"""
Evaluation script for code understanding tasks.
Input: json data + config dict
Output: float score, saves log and result files
"""
import json
import os
from pathlib import Path
from typing import Dict, List
import re
import sys

from openai import OpenAI

sys.path.append(str(Path(__file__).parent))

MAX_PATCH_LEN = 50000
MAX_ANSWER_LEN = 100000

def _call_llm(system_prompt: str, 
             user_content: str,
             openai_base_url: str,
             openai_api_key: str,
             openai_model_id: str,
             timeout: int = 120) -> str:
    """
    Call Claude LLM API using OpenAI-compatible interface

    This function maintains compatibility with existing modules while using the new Claude API format.

    Args:
        system_prompt: System prompt
        user_content: User content
        openai_base_url: Claude API base URL
        openai_api_key: API key for Claude API
        openai_model_id: Model ID to use for the API call
        timeout: Timeout duration (currently not used with OpenAI client)

    Returns:
        LLM response content
    """
    try:
        client = OpenAI(
            base_url=openai_base_url,
            api_key=openai_api_key
        )
       # print(f"-------------------{ClaudeAPIConfig.get_model(model)}---------------")
        completion = client.chat.completions.create(
            model=openai_model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return completion.choices[0].message.content

    except Exception as e:
        return f"[ERROR] {e}\nRESULT: FAIL"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n\n[truncated from {len(text)} chars]"


def _extract_answer_section(full_answer: str, q_num: int) -> str:
    patterns = [
        rf'#+\s*{q_num}[\.\)]\s*(.+?)(?=#+\s*{q_num + 1}[\.\)]|\Z)',
        rf'\*\*{q_num}[\.\)]\*\*\s*(.+?)(?=\*\*{q_num + 1}[\.\)]|\Z)',
        rf'^{q_num}[\.\)]\s*(.+?)(?=^{q_num + 1}[\.\)]|\Z)',
    ]
    for pattern in patterns:
        match = re.search(pattern, full_answer, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return full_answer


def _build_prompt(question: str, checklist: List[Dict], answer: str, patch: str = "") -> str:
    items = [f"- {item['item_id']}: {item['description']}" for item in checklist]
    
    patch_part = ""
    if patch:
        patch_part = f"\n[PR Context]:\n{_truncate(patch, MAX_PATCH_LEN)}\n"
    
    answer = _truncate(answer, MAX_ANSWER_LEN)
    
    return f"""Evaluate if the answer satisfies the question requirements.

QUESTION:
{question}

REQUIREMENTS:
{chr(10).join(items)}
{patch_part}
ANSWER:
{answer}

RULES:
1. Answer MUST use clear English explanations, NOT just code diffs
2. Score = (satisfied items) / (total items), give 1.0 only when ALL items satisfied
3. Give 0.0 when answer is just code diffs or completely wrong

Respond with JSON only:
{{
    "reasoning": "brief explanation", 
    "score": 0.0-1.0, 
    "satisfied_items": ["item_id1", ...]
}}
"""


def _judge_question(
        q_id: str, 
        q_text: str, 
        checklist: List[Dict], 
        answer: str, 
        patch: str,
        openai_base_url: str,
        openai_api_key: str,
        openai_model_id: str
    ) -> tuple:
    prompt = _build_prompt(q_text, checklist, answer, patch)
    system = "You are an expert evaluator for code understanding questions."
    
    try:
        response = _call_llm(
            system_prompt=system,
            user_content=prompt,
            openai_base_url=openai_base_url,
            openai_api_key=openai_api_key,
            openai_model_id=openai_model_id
        )
        
        if response.startswith("[ERROR]"):
            raise Exception(f"API error: {response}")
        
        content = response.strip()
        if content.startswith("```"):
            content = content[content.find('\n')+1:]
        if content.endswith("```"):
            content = content[:-3]
        
        start = content.find('{')
        end = content.rfind('}')
        if start == -1 or end == -1:
            raise Exception("No valid JSON found")
        
        result = json.loads(content[start:end + 1])
        score = float(result.get("score", 0.0))
        reasoning = result.get("reasoning", "")
        
        return q_id, score, reasoning
        
    except Exception as e:
        return q_id, 0.0, f"Error: {e}"


def run_code_understanding(data, log_dir, model_name, api_key, base_url) -> float:
    """
    Evaluate code understanding for a single instance.
    
    Args:
        data: JSON data dict containing:
            - instance_id: str
            - questions: dict with "questions" key or list of question dicts
            - checklists: dict with "checklist_categories"
            - model_patch: str (model's answer)
            - test_patch: str (optional, PR context)
        - base_url: str (must, base URL for API calls)
        - api_key: str (must, API key)
        - model_name: str (must, model ID for API calls)
    Returns:
        float: Average score (0.0-1.0)
    """
    instance_id = data.get("instance_id", "unknown")
    
    questions = data.get("questions", {})
    checklists = data.get("checklists", {})
    model_patch = data.get("model_patch", "")
    test_patch = data.get("test_patch", "")
    
    out_dir = os.path.join(log_dir, instance_id)
    os.makedirs(out_dir, exist_ok=True)
    
    safe_id = instance_id.replace('/', '_')
    
    if not model_patch or not model_patch.strip():
        return 0.0
    
    if isinstance(questions, dict):
        questions = questions.get("questions", [])
    
    if not questions:
        return 0.0
    
    # Build checklist map
    checklist_map = {}
    for category, items in checklists.get("checklist_categories", {}).items():
        for item in items:
            checklist_map[item['item_id']] = item
    
    # Judge each question
    results = []
    for idx, q in enumerate(questions, 1):
        q_id = q['question_id']
        q_text = q['question_text']
        related = q.get('related_checklist_items', [])
        
        answer_section = _extract_answer_section(model_patch, idx)
        items = [checklist_map[item_id] for item_id in related if item_id in checklist_map]
        
        result = _judge_question(
            q_id=q_id, 
            q_text=q_text, 
            checklist=items, 
            answer=answer_section, 
            patch=test_patch,
            openai_base_url=base_url,
            openai_api_key=api_key,
            openai_model_id=model_name
        )
        results.append(result)
    
    # Calculate average score
    scores = [r[1] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    
    # Build details
    details = {
        "instance_id": instance_id,
        "average_score": avg_score,
        "question_scores": {r[0]: {"score": r[1], "reasoning": r[2]} for r in results}
    }
        
    # Save result
    if out_dir:
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        result_file = out_path / f"{safe_id}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(details, f, indent=2, ensure_ascii=False)
    
    return avg_score