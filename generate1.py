import json
import re
import os
import time
import argparse
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# RuleGenerator 类
class RuleGenerator:
    def __init__(self, api_key, model_name, base_url="https://api-inference.huggingface.co"):
        # 使用 Hugging Face API 正确的基础 URL
        self.client = InferenceClient(api_key=api_key, base_url=base_url)
        self.model_name = model_name

    def analyze_log(self, log_text, log_fields):
        # 预处理日志，移除优先级字段
        preprocessed_log = re.sub(r'<\d+>', '', log_text)

        # 生成规则的提示内容
        prompt = f"""请根据以下带标签的日志生成解析规则。请以 JSON 格式输出规则，规则格式如下：
{{
  "pattern": "<正则表达式，要求使用 Python 的命名捕获组，如 (?P<field_name>...)>",
  "fields": [
    {{"name": "字段名称", "type": "字段类型", "example": "示例值"}}
  ],
  "priority": 数值,
  "examples": ["日志示例"]
}}
请确保输出合法的 JSON且不要包含任何其他文字。

日志内容：{preprocessed_log}
标注字段：{json.dumps(log_fields, ensure_ascii=False, indent=2)}
"""

        # 最大重试次数
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 调用 Huggingface API 获取生成的规则
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=2000
                )
                output = response.choices[0].message.content.strip()

                if not output:
                    raise ValueError("API 返回为空")

                # 尝试解析规则
                rule = json.loads(output)
                return rule
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"错误：{str(e)}")
                    return None
                print(f"重试第 {retry_count} 次... 错误信息：{str(e)}")
                time.sleep(1)  # 等待 1 秒后重试


# generate 函数
def generate(labeled_data_file, rules_file, api_key, model_name, base_url="https://api-inference.huggingface.co"):
    generator = RuleGenerator(api_key, model_name, base_url)

    with open(labeled_data_file, encoding="utf-8") as f:
        data = json.load(f)

    rules_dict = {}  # 用于去重的规则字典
    error_logs = []  # 错误日志

    for i, item in enumerate(data):
        try:
            rule = generator.analyze_log(item['logText'], item['logField'])
            if rule:
                pattern = rule.get("pattern", "").strip()
                if not pattern:
                    error_logs.append(f"日志 {i+1} 未生成正则表达式")
                    continue
                try:
                    re.compile(pattern)
                except re.error as e:
                    error_logs.append(f"日志 {i+1} 无效正则表达式：{str(e)}")
                    continue

                if pattern in rules_dict:
                    existing_ex = rules_dict[pattern].get("examples", [])
                    new_ex = rule.get("examples", [])
                    for ex in new_ex:
                        if ex not in existing_ex:
                            existing_ex.append(ex)
                    rules_dict[pattern]["examples"] = existing_ex
                else:
                    rules_dict[pattern] = rule

        except Exception as e:
            error_logs.append(f"日志 {i+1} 处理失败：{str(e)}")
            continue

    final_rules = list(rules_dict.values())

    # 保存规则到文件
    with open(rules_file, "w", encoding="utf-8") as f:
        json.dump(final_rules, f, indent=2, ensure_ascii=False)

    # 返回错误日志
    return final_rules, error_logs


# 处理命令行参数
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # 添加命令行参数
    parser.add_argument("--labeled_data_file_path", required=True, help="标签数据文件路径")
    parser.add_argument("--rules_save_file_path", required=True, help="规则保存文件路径")
    parser.add_argument("--api_key", required=True, help="Hugging Face API 密钥")
    parser.add_argument("--base_url", default="https://api-inference.huggingface.co", help="Hugging Face API 基础 URL (可选，默认为 https://api-inference.huggingface.co )")
    parser.add_argument("--use_llm_model", required=True, help="选择要使用的大模型（例如：Qwen/Qwen2.5-72B-Instruct）")

    args = parser.parse_args()

    # 获取命令行参数
    labeled_data_file = args.labeled_data_file_path
    rules_save_file = args.rules_save_file_path
    api_key = args.api_key
    base_url = args.base_url
    model_name = args.use_llm_model  # 从命令行参数中获取模型名称

    # 调用生成函数
    generate(labeled_data_file, rules_save_file, api_key, model_name, base_url)
