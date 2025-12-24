import json
from datasets import load_dataset
from tqdm import tqdm

config_names = [
    "code_understanding",
    "configuration_deployment",
    "performance_optimization",
    "test_case_generation",
    "opensource-swe-bench-live",
    "opensource-swe-bench-multilingual",
    "opensource-swe-bench-verified",
    "opensource-swe-Rebench",
    "selected"
]

output_file = "./data/swecompass_all_2000.jsonl"

print(f"🚀 开始下载并合并数据到: {output_file}")

with open(output_file, 'w', encoding='utf-8') as f_out:
    for config in config_names:
        print(f"\n📥 正在处理子集: {config} ...")
        
        try:
            ds = load_dataset("Kwaipilot/SWE-Compass", config, split="test")
            
            count = 0
            for row in tqdm(ds, desc=f"Writing {config}"):
                f_out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                count += 1
                
            print(f"✅ {config} 完成，共写入 {count} 条数据。")
            
        except Exception as e:
            print(f"❌ 处理 {config} 时出错: {e}")

print(f"\n🎉 所有数据合并完成！文件保存为: {output_file}")
