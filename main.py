import streamlit as st
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import os
import json
import re
import tempfile

from generate import RuleGenerator
# 加载环境变量
load_dotenv()
api_key = os.getenv("HUGGINGFACE_API_KEY")
client = InferenceClient(api_key=api_key)

# 初始化会话状态
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'generated_rules' not in st.session_state:
    st.session_state.generated_rules = []
if 'parsed_logs' not in st.session_state:
    st.session_state.parsed_logs = []

# 设置页面标题
st.title("智能日志解析系统")

# 创建侧边栏用于参数调整
st.sidebar.header("核心功能")

# 模型选择
models = [
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "CohereForAI/c4ai-command-r-plus-08-2024",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
    "Qwen/QwQ-32B-Preview",
    "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "NousResearch/Hermes-3-Llama-3.1-8B",
    "mistralai/Mistral-Nemo-Instruct-2407",
    "microsoft/Phi-3.5-mini-instruct"
]

selected_model = st.sidebar.selectbox(
    "选择AI模型",
    models,
    index=0,
    format_func=lambda x: x.split("/")[-1]
)

# 主功能选项卡
tab1, tab2, tab3 = st.tabs(["实时解析", "规则生成", "批量处理"])

# 实时解析功能
with tab1:
    st.subheader("实时日志解析")
    
    # 输入方式选择
    input_method = st.radio("输入方式：", ["手动输入", "上传文件"], horizontal=True)
    
    if input_method == "手动输入":
        log_input = st.text_area("输入日志内容：", height=150)
        if st.button("立即解析"):
            if log_input:
                with st.spinner("正在解析..."):
                    try:
                        # 预处理日志，移除优先级字段
                        preprocessed_log = re.sub(r'<\d+>', '', log_input)
                        response = client.chat.completions.create(
                            model=selected_model,
                            messages=[{
                                "role": "user",
                                "content": f"解析以下日志：\n{preprocessed_log}\n要求：1.生成正则表达式 2.提取关键字段"
                            }],
                            temperature=0.2,
                            max_tokens=1000
                        )
                        result = response.choices[0].message.content
                        st.code(result, language="markdown")
                        st.session_state.messages.append({"log": log_input, "result": result})
                    except Exception as e:
                        st.error(f"解析失败：{str(e)}")
    
    else:
        uploaded_file = st.file_uploader("上传日志文件（JSON格式）", type=["json"])
        if uploaded_file:
            try:
                data = json.load(uploaded_file)
                st.success(f"成功加载 {len(data)} 条日志")
                if st.button("批量解析"):
                    progress_bar = st.progress(0)
                    results = []
                    for i, item in enumerate(data):
                        try:
                            # 预处理日志，移除优先级字段
                            preprocessed_log = re.sub(r'<\d+>', '', item['logText'])
                            response = client.chat.completions.create(
                                model=selected_model,
                                messages=[{
                                    "role": "user",
                                    "content": f"解析日志：{preprocessed_log}\n生成正则表达式并提取字段"
                                }],
                                temperature=0.2,
                                max_tokens=800
                            )
                            results.append(response.choices[0].message.content)
                            progress_bar.progress((i+1)/len(data))
                        except Exception as e:
                            results.append(f"解析失败：{str(e)}")
                    st.session_state.parsed_logs = results
                    st.success("批量解析完成！")
                
                if st.session_state.parsed_logs:
                    st.download_button(
                        label="下载解析结果",
                        data=json.dumps(st.session_state.parsed_logs, indent=2, ensure_ascii=False),
                        file_name="parsed_results.json"
                    )
                
            except Exception as e:
                st.error(f"文件解析错误：{str(e)}")

# 规则生成功能（生成 flat 结构规则）
with tab2:
   st.subheader("上传开发集数据（带标签）")

   dev_file = st.file_uploader("上传开发集数据（JSON格式）", type=["json"], key="dev_upload")

   if dev_file:
        try:
            dev_data = json.load(dev_file)
            st.success(f"已加载开发集数据：{len(dev_data)} 条日志")

            if st.button("生成解析规则"):
                # 初始化 RuleGenerator
                generator = RuleGenerator(api_key=api_key, model_name=selected_model)

                progress_bar = st.progress(0)
                rules_dict = {}  # 用于去重的规则字典
                error_logs = []  # 错误日志

                for i, item in enumerate(dev_data):
                    try:
                        # 调用规则生成方法
                        rule = generator.analyze_log(
                            log_text=item['logText'],
                            log_fields=item['logField']
                        )

                        if not rule:
                            error_logs.append(f"日志 {i+1} 规则生成失败")
                            continue

                        # 验证正则表达式的有效性
                        pattern = rule.get("pattern", "").strip()
                        if not pattern:
                            error_logs.append(f"日志 {i+1} 未生成正则表达式")
                            continue

                        try:
                            re.compile(pattern)
                        except re.error as e:
                            error_logs.append(f"日志 {i+1} 无效正则表达式：{str(e)}")
                            continue

                        # 聚合同一正则表达式的规则，合并示例
                        if pattern in rules_dict:
                            existing_ex = rules_dict[pattern].get("examples", [])
                            new_ex = rule.get("examples", [])
                            for ex in new_ex:
                                if ex not in existing_ex:
                                    existing_ex.append(ex)
                            rules_dict[pattern]["examples"] = existing_ex
                        else:
                            rules_dict[pattern] = rule

                        progress_bar.progress((i+1) / len(dev_data))

                    except Exception as e:
                        error_logs.append(f"日志 {i+1} 处理失败：{str(e)}")
                        continue

                # 显示错误信息
                if error_logs:
                    st.error("处理过程中发生以下错误：\n" + "\n".join(error_logs))

                # 保存并展示生成的规则
                final_rules = list(rules_dict.values())
                st.session_state.generated_rules = final_rules

                # 使用 tempfile 保存文件路径，避免污染工作目录
                with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp_file:
                    temp_file_path = temp_file.name
                    with open(temp_file_path, 'w', encoding='utf-8') as f:
                        json.dump(final_rules, f, indent=2, ensure_ascii=False)

                # 展示生成的规则
                st.subheader("生成的解析规则")
                for idx, rule in enumerate(final_rules, 1):
                    st.markdown(f"**规则 {idx}**")
                    st.code(json.dumps(rule, indent=2, ensure_ascii=False), language="json")

                # 提供下载按钮
                st.download_button(
                    label="下载规则文件",
                    data=json.dumps(final_rules, indent=2, ensure_ascii=False),
                    file_name="classified_rules.json"
                )

                # 删除临时文件
                os.remove(temp_file_path)

        except Exception as e:
            st.error(f"开发集处理错误：{str(e)}")

# 批量处理功能（调用 extract.py，不使用大模型）
with tab3:
    st.subheader("批量日志处理")
    
    # 上传规则文件
    rule_file = st.file_uploader("上传规则文件", type=["json"], key="rule_upload")
    # 上传数据文件
    eval_file = st.file_uploader("上传评估集数据（无标签）", type=["json"], key="eval_upload")
    
    if rule_file and eval_file:
        try:
            # 保存上传的文件
            with open("temp_rules.json", "wb") as f:
                f.write(rule_file.getbuffer())
            with open("temp_data.json", "wb") as f:
                f.write(eval_file.getbuffer())
            
            if st.button("开始解析"):
                # 注意：extract.py 中不再使用大模型
                from extract import LogParser
                parser = LogParser("temp_rules.json")
                
                # 加载数据
                with open("temp_data.json", encoding="utf-8") as f:
                    eval_data = json.load(f)
                
                # 解析数据
                results = []
                progress_bar = st.progress(0)
                for i, item in enumerate(eval_data):
                    fields = parser.parse_log(item["logText"])
                    results.append({
                        "logText": item["logText"],
                        "logFields": fields
                    })
                    progress_bar.progress((i+1)/len(eval_data))
                
                st.session_state.parsed_logs = results
                st.success("解析完成！")
                
                st.download_button(
                    label="下载解析结果",
                    data=json.dumps(results, indent=2, ensure_ascii=False),
                    file_name="parsed_results.json"
                )
        
        except Exception as e:
            st.error(f"处理错误：{str(e)}")
        finally:
            # 清理临时文件
            if os.path.exists("temp_rules.json"):
                os.remove("temp_rules.json")
            if os.path.exists("temp_data.json"):
                os.remove("temp_data.json")

# 历史记录功能
with st.expander("查看历史记录"):
    if st.session_state.messages:
        for idx, msg in enumerate(st.session_state.messages):
            st.write(f"**记录 {idx+1}**")
            st.code(f"原始日志：\n{msg['log']}", language="text")
            st.code(f"解析结果：\n{msg['result']}", language="markdown")
    else:
        st.info("暂无历史记录")

# 清除会话按钮
if st.button("清除所有会话"):
    st.session_state.messages = []
    st.session_state.generated_rules = []
    st.session_state.parsed_logs = []
    st.experimental_rerun()
