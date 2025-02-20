import json
import re
import argparse
from tqdm import tqdm
import Levenshtein


def clean_log_text(log_text, use_extra_clean=False):
    # 去除前后空白字符和不可见字符
    log_text = log_text.strip()
    log_text = re.sub(r'^[\s\u200B-\u200D\uFEFF]+', '', log_text)
    log_text = re.sub(r'[\s\u200B-\u200D\uFEFF]+$', '', log_text)
    if use_extra_clean:
        # 去除一些可能影响匹配的特殊符号，仅保留字母、数字、空格和冒号
        log_text = re.sub(r'[^\w\s:]', '', log_text)
    return log_text


class LogParser:
    def __init__(self, rules_file):
        # 加载平铺结构的规则列表
        with open(rules_file, encoding="utf-8") as f:
            self.rules = json.load(f)
        self._compile_rules(use_extra_replace=False)

    def _compile_rules(self, use_extra_replace=False):
        """编译所有规则中的正则表达式，并存入 rule['compiled']"""
        for rule in self.rules:
            try:
                if use_extra_replace:
                    # 将 \- 替换为下划线 _
                    rule["pattern"] = re.sub(r"\\-", "_", rule["pattern"])
                rule["compiled"] = re.compile(rule["pattern"])
                print(f"[DEBUG] 规则编译成功：{rule['pattern']}")
            except re.error as e:
                print(f"规则编译失败：{rule['pattern']} - {str(e)}")

    def parse_log(self, log_text):
        log_text = clean_log_text(log_text, use_extra_clean=False)
        print(f"[DEBUG] 待匹配的日志文本: {log_text}")
        """遍历所有规则，匹配成功则返回匹配到的命名捕获组字段，若有多个匹配则选择 priority 最高的规则"""
        matched = []
        for rule in self.rules:
            if "compiled" not in rule:
                continue
            print(f"[DEBUG] 尝试用规则 {rule['pattern']} 匹配日志：{log_text}")
            m = rule["compiled"].search(log_text)
            if m:
                print(f"[DEBUG] 匹配成功：{rule['pattern']}")
                matched.append((rule, m))
        if not matched:
            print(f"[DEBUG] 没有找到匹配规则：{log_text}")
            # 对无标签日志使用额外清洗和规则处理
            log_text_similarity = clean_log_text(log_text, use_extra_clean=True)
            self._compile_rules(use_extra_replace=True)
            # 找出与各规则的相似度
            similarities = self.find_similarities(log_text_similarity)
            most_similar_rule = self.find_most_similar_rule(similarities)
            if most_similar_rule:
                print(f"[DEBUG] 尝试使用最相似规则 {most_similar_rule['pattern']} 匹配日志：{log_text_similarity}")
                m = most_similar_rule["compiled"].search(log_text_similarity)
                if m:
                    print(f"[DEBUG] 最相似规则匹配成功：{most_similar_rule['pattern']}")
                    group_dict = m.groupdict()
                    return [{"name": k, "value": (v.strip() if v else "")} for k, v in group_dict.items()], None
                else:
                    print(f"[DEBUG] 最相似规则 {most_similar_rule['pattern']} 匹配失败，日志文本: {log_text_similarity}")
            # 输出各规则相似度信息
            print("\n各规则与该日志的相似度：")
            for idx, (rule, sim) in enumerate(similarities):
                print(f"规则 {idx + 1}（正则: {rule['pattern']}）相似度: {sim}")
            return [], "没有找到匹配规则"

        # 按 priority（优先级数值越大优先）选择规则，若无 priority 则视为 0
        selected_rule, selected_match = max(matched, key=lambda x: x[0].get("priority", 0))
        group_dict = selected_match.groupdict()
        return [{"name": k, "value": (v.strip() if v else "")} for k, v in group_dict.items()], None

    def find_similarities(self, log_text):
        """计算日志文本与各规则的相似度"""
        similarities = []
        for rule in self.rules:
            min_distance = float('inf')
            for example in rule.get("examples", []):
                distance = Levenshtein.distance(log_text, example)
                if distance < min_distance:
                    min_distance = distance
            similarity = 1 - (min_distance / max(len(log_text), max(len(example) for example in rule.get("examples", [""]))))
            similarities.append((rule, similarity))
        return similarities

    def find_most_similar_rule(self, similarities):
        """从相似度列表中找出最相似的规则"""
        most_similar = max(similarities, key=lambda x: x[1])
        if most_similar[1] > 0:
            return most_similar[0]
        return None


def extract(unlabeled_data_file_path: str, rules_save_file_path: str, result_file_path: str) -> None:

    parser = LogParser(rules_save_file_path)

    with open(unlabeled_data_file_path, 'r', encoding="utf-8") as f:
        data = json.load(f)

    results = []
    unmatched_logs = []  # 用于记录没有匹配上的日志

    for item in tqdm(data, desc="解析日志"):
        fields, reason = parser.parse_log(item['logText'])

        if reason:
            unmatched_logs.append({
                "logText": item["logText"],
                "reason": reason
            })

        item['logField'] = fields
        results.append(item)

    with open(result_file_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"\n解析完成，结果已保存到：{result_file_path}")

    if unmatched_logs:
        print("\n以下日志未能匹配到规则：")
        for log in unmatched_logs:
            print(f"日志内容：{log['logText']}")
            print(f"原因：{log['reason']}")
            print("-" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--unlabeled_data_file_path", required=True, help="待解析的无标签数据路径")
    parser.add_argument("--rules_save_file_path", required=True, help="规则文件路径")
    parser.add_argument("--result_file_path", required=True, help="解析结果保存路径")

    args = parser.parse_args()

    extract(args.unlabeled_data_file_path, args.rules_save_file_path, args.result_file_path)