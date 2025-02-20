import json
import re
import os
import time
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
api_key = os.getenv("HUGGINGFACE_API_KEY")

class RuleGenerator:
    def __init__(self, api_key, model_name):
        self.client = InferenceClient(api_key=api_key)
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

def generate(labeled_data_file, rules_file, api_key, model_name):
    generator = RuleGenerator(api_key, model_name)

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

if __name__ == "__main__":
    # 保证直接运行时也能执行生成规则的过程
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--labeled_data_file", required=True)
    parser.add_argument("--rules_file", default="classified_rules.json")
    parser.add_argument("--api_key", required=True)
    parser.add_argument("--model", default="Qwen/Qwen2.5-72B-Instruct")

    args = parser.parse_args()
    generate(args.labeled_data_file, args.rules_file, args.api_key, args.model)
