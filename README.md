本项目使用了github开源项目HuggingQwen-Assistant，仓库为https://github.com/nicekate/HuggingQwen-Assistant.git

# Automated-generation-algorithm-for-log-parsing-rules
基于Streamlit开发的交互式应用，集成了Hugging Face的大型语言模型。结合传统正则表达式规则挖掘与深度学习语义分析实现日志解析规则的自动化算法
## 功能特点

- 使用Hugging Face的大型语言模型
- 通过 OpenAI 的 API，基于给定的日志文本（logText）和标注字段（logField）请求生成解析规则
- 支持选择不同模型，如Qwen2.5，DeepSeek-R1等
- 允许用户自定义和管理系统提示
- 可选择不同功能，包括实时解析，规则生成，批量处理等
- 支持解析历史查看和清除
- 错误重试机制，提高稳定性：如果生成规则时发生错误（如 JSON 解析错误），会自动重试最多 3 次。

## 安装说明

1. 克隆仓库到本地：

   ```
   git clone https://github.com/hlcccc/Automated-generation-algorithm-for-log-parsing-rules.git
   cd Automated-generation-algorithm-for-log-parsing-rules
   ```

2. 安装依赖：

   ```
   pip install -r requirements.txt
   ```


## 使用方法一：网页api连接大模型使用 （对应extract.py，generate.py）

1. 获取Hugging Face API密钥：
   - 访问 [https://huggingface.co/settings/tokens/new?globalPermissions=inference.serverless.write&tokenType=fineGrained](https://huggingface.co/settings/tokens/new?globalPermissions=inference.serverless.write&tokenType=fineGrained) 创建新的API token。
   - 确保选择了 `inference.serverless.write` 权限。

2. 复制`.env.example`文件并重命名为`.env`，然后在其中填入你的Hugging Face API密钥：

   ```
   HUGGINGFACE_API_KEY=你的api密钥
   ```

3. 运行应用：

   ```
   streamlit run app.py
   ```

4. 在浏览器中打开显示的本地地址（通常是 http://localhost:8501）

5. 在侧边栏选择或自定义系统提示，调整模型参数

6. 手动输入或上传文件即可解析文本/生成规则，还可进行批量处理

7. 提供历史记录查询，使用"清除所有对话"按钮可以重置对话


## 使用方法二：输入指令通过api连接大模型使用（本比赛指定方式，可用于自动化评测，对应extract1.py，generate1.py）

1.extract1.py的测试命令

执行以下命令运行生成阶段的代码:

   ```
python generate1.py --labeled_data_file_path "LABELED_DATA_FILE_PATH" --rules_save_file_path "RULES_SAVE_FILE_PATH" \
    --api_key "API_KEY" --base_url "BASE_URL" --use_llm_model "USE_LLM_MODEL"
   ```

样例如下:python generate1.py --labeled_data_file_path "E:\web security\1\4\1\2\test.json" --rules_save_file_path "E:\web security\1\4\1\2\rules.json" --api_key "xxx" --base_url "https://api-inference.huggingface.co" --use_llm_model "Qwen/Qwen2.5-72B-Instruct"

执行以下命令运行提取阶段的代码:

   ```
python extract1.py --unlabeled_data_file_path "UNLABELED_DATA_FILE_PATH" --rules_save_file_path "RULES_SAVE_FILE_PATH" \
    --result_file_path "RESULT_FILE_PATH"
   ```

样例如下：python extract1.py --unlabeled_data_file_path "E:\web security\1\4\1\2\test1.json" --rules_save_file_path "E:\web security\1\4\1\2\classified_rules(61).json" --result_file_path "E:\web security\1\4\1\2\result1.json"



## 使用方法三：本地部署后使用
1.设置本地 LLM 模型
generate2.py是openai的接口连接本地部署的模型

运行脚本

   ```
python generate2.py --labeled_data_file <labeled_data_file_path> --rules_file <output_rules_file_path> --model <model_name>
   ```
--labeled_data_file：提供输入的已标注日志文件路径（JSON格式）。
--rules_file：生成的解析规则文件输出路径（JSON格式）。
--model：指定本地模型名称，默认为 qwen2.5:7b。


## 自定义提示词

- 你可以在应用的侧边栏中添加、选择或删除自定义的系统提示
- 自定义提示词会保存在`custom_prompts.json`文件中

## 注意事项

- 请确保你有足够的Hugging Face API使用额度
- 大型语言模型可能会产生不准确或不适当的内容，请谨慎使用

## 许可证

[MIT License](LICENSE)