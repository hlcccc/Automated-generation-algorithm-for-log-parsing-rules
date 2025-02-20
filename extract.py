import json
import re
import argparse
from tqdm import tqdm
import Levenshtein


def clean_log_text(log_text, use_extra_clean=False):
    log_text = log_text.strip()
    log_text = re.sub(r'^[\s\u200B-\u200D\uFEFF]+', '', log_text)
    log_text = re.sub(r'[\s\u200B-\u200D\uFEFF]+$', '', log_text)
    if use_extra_clean:
        log_text = re.sub(r'[^\w\s:]', '', log_text)
    return log_text


class LogParser:
    def __init__(self, rules_file):
        with open(rules_file, encoding="utf-8") as f:
            self.rules = json.load(f)
        self._compile_rules()

    def _compile_rules(self, use_extra_replace=False):
        for rule in self.rules:
            try:
                pattern = rule["pattern"]
                if use_extra_replace:
                    pattern = re.sub(r"\\-", "_", pattern)
                compiled = re.compile(pattern)
                rule["compiled"] = compiled
                rule["field_names"] = list(compiled.groupindex.keys())
            except re.error as e:
                print(f"规则编译失败：{rule['pattern']} - {str(e)}")

    def parse_log(self, log_text):
        log_text = clean_log_text(log_text)
        matched = []
        for rule in self.rules:
            if "compiled" not in rule:
                continue
            m = rule["compiled"].search(log_text)
            if m:
                matched.append((rule, m))
        if matched:
            selected_rule, selected_match = max(matched, key=lambda x: x[0].get("priority", 0))
            group_dict = selected_match.groupdict()
            return [{"name": k, "value": v.strip() if v else ""} for k, v in group_dict.items()], None

        log_text_clean = clean_log_text(log_text, use_extra_clean=True)
        temp_rules = []
        for r in self.rules:
            try:
                temp_rule = r.copy()
                temp_rule["pattern"] = re.sub(r"\\-", "_", temp_rule["pattern"])
                compiled = re.compile(temp_rule["pattern"])
                temp_rule["compiled"] = compiled
                temp_rule["field_names"] = list(compiled.groupindex.keys())
                temp_rules.append(temp_rule)
            except re.error as e:
                continue

        if not temp_rules:
            return [], "所有规则均无效"

        similarities = []
        for temp_rule in temp_rules:
            min_dist = float('inf')
            for example in temp_rule.get("examples", []):
                dist = Levenshtein.distance(log_text_clean, example)
                if dist < min_dist:
                    min_dist = dist
            max_len = max(len(log_text_clean), max((len(e) for e in temp_rule.get("examples", [""])), default=1))
            similarity = 1 - (min_dist / max_len)
            similarities.append((temp_rule, similarity))

        if not similarities:
            return [], "无法计算相似度"

        most_similar_rule = max(similarities, key=lambda x: (x[1], x[0].get("priority", 0)))[0]
        m = most_similar_rule["compiled"].search(log_text_clean)
        group_dict = m.groupdict() if m else {fn: "" for fn in most_similar_rule.get("field_names", [])}
        fields = [{"name": k, "value": v.strip() if v else ""} for k, v in group_dict.items()]
        return fields, None


def process_data(input_file, output_file, rules_file):
    parser = LogParser(rules_file)
    with open(input_file, 'r', encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for item in tqdm(data, desc="解析日志"):
        fields, _ = parser.parse_log(item['logText'])
        item['logField'] = fields
        results.append(item)
    with open(output_file, 'w', encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"解析完成，结果保存至：{output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", required=True)
    parser.add_argument("--output_file", required=True)
    parser.add_argument("--rules_file", default="classified_rules.json")
    args = parser.parse_args()
    process_data(args.input_file, args.output_file, args.rules_file)