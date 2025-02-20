import json
import argparse
import re
from dotenv import load_dotenv
import os
import time
from openai import OpenAI

# 初始化客户端连接

client = OpenAI(
    base_url='http://localhost:11434/v1/',
    api_key='ollama',  # 本地部署可忽略
)


def get_chat_completions(messages, api_key, base_url, use_llm_model, model_name, prompt):
    global client
    client = OpenAI(
        base_url='http://localhost:11434/v1/',
        api_key='ollama',  # 本地部署可忽略
    )
    response = client.chat.completions.create(
                    model= model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=2000,
                    response_format={"type": "json_object"}  # 强制返回JSON格式
                )
    return response


class RuleGenerator:
    def __init__(self, model_name):
        self.model_name = model_name

    def analyze_log(self, log_text, log_fields):
        preprocessed_log = re.sub(r'<\d+>', '', log_text)
        prompt = f"""请根据以下带标签的日志生成解析规则。请特别注意：
        1. 必须严格保留原始日志中的下划线(_)和连字符(-)符号，生成规则时不得混淆使用
        2. 设备名称等复合字段需要严格按原始分隔符拆分（如 ZX_HXJF_D_S7712-01 生成规则时应拆分为：前四段用下划线连接，最后一段用连字符连接）
        3. 时间戳等固定格式字段需按实际字符匹配

        请以 JSON 格式输出规则，规则格式如下：
        {{
          "pattern": "<使用 Python 命名捕获组的正则表达式>",
          "fields": [
            {{"name": "字段名", "type": "字段类型", "example": "示例值"}}
          ],
          "priority": 数值,
          "examples": ["日志示例"]
        }}

        关键注意事项：
        - 设备名称的正则模式需反映实际分隔符（如 ZX_HXJF_D_S7712-01 应表示为 \\w+_\\w+_\\w+_\\w+-\d+）
        - 不要将下划线和连字符混用，如避免使用 [\\w-]+ 这种模糊匹配
        - 优先使用字面字符匹配固定分隔符（如 %% 应原样保留）

        日志内容：{preprocessed_log}
        标注字段：{json.dumps(log_fields, ensure_ascii=False, indent=2)}
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = get_chat_completions(None, None, None, None, self.model_name, prompt)
                output = response.choices[0].message.content

                # 清理响应内容（保持原有处理逻辑不变）
                cleaned_output = re.sub(r'^[^\{]*', '', output)
                cleaned_output = re.sub(r'[^\}]*$', '', cleaned_output)

                rule = json.loads(cleaned_output)

                # 保持原有后处理逻辑不变
                return rule
            except json.JSONDecodeError as e:
                retry_count += 1
                print(f"JSON解析失败，重试第{retry_count}次...")
                time.sleep(1)
            except Exception as e:
                print(f"发生错误：{str(e)}")
                break
        return None


def generate(labeled_data_file, rules_file, model_name):
    generator = RuleGenerator(model_name)

    with open(labeled_data_file, encoding="utf-8") as f:
        data = json.load(f)

    rules_dict = {}
    for item in data:
        rule = generator.analyze_log(item['logText'], item['logField'])
        if rule:
            # 保持原有验证和去重逻辑不变
            pattern = rule.get("pattern", "").strip()
            if pattern and re.compile(pattern):
                if pattern in rules_dict:
                    rules_dict[pattern]["examples"] = list(
                        set(rules_dict[pattern]["examples"] + rule.get("examples", []))
                    )
                else:
                    rules_dict[pattern] = rule

    with open(rules_file, "w", encoding="utf-8") as f:
        json.dump(list(rules_dict.values()), f, indent=2, ensure_ascii=False)

    print(f"规则生成完成：{rules_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--labeled_data_file", required=True)
    parser.add_argument("--rules_file", default="classified_rules.json")
    parser.add_argument("--model", default="qwen2.5:7b")  # 适配本地模型名称

    args = parser.parse_args()
    generate(args.labeled_data_file, args.rules_file, args.model)