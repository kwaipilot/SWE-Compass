import json
from datasets import load_dataset
from tqdm import tqdm

# 1. 定义所有需要下载的 config 名称
config_names = [
    "code_understanding",
    "configuration_deployment",
    "performance_optimization",
    "test_case_generation",
    "opensource_swe_bench_live",
    "opensource_swe_bench_multilingual",
    "opensource_swe_bench_verified",
    "opensource_swe_Rebench",
    "selected"
]

# 输出文件名
output_file = "./data/swecompass_all_2000.jsonl"

print(f"🚀 开始下载并合并数据到: {output_file}")

# 2. 打开文件准备写入
with open(output_file, 'w', encoding='utf-8') as f_out:
    for config in config_names:
        print(f"\n📥 正在处理子集: {config} ...")
        
        try:
            # 加载特定子集（split 为 eval）
            ds = load_dataset("Kwaipilot/SWE-Compass", config, split="eval")
            
            count = 0
            for row in tqdm(ds, desc=f"Writing {config}"):
                f_out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                count += 1
                
            print(f"✅ {config} 完成，共写入 {count} 条数据。")
            
        except Exception as e:
            print(f"❌ 处理 {config} 时出错: {e}")

print(f"\n🎉 所有数据合并完成！文件保存为: {output_file}")
