"""评判Agent - 负责质量把关和纠错引导"""

import json

from agent.client import LLMClient

JUDGE_SYSTEM_PROMPT = """你是 DeepPulse 的评判Agent（Judge Agent），在主分析Agent完成分析后介入。

## 核心职责
你的任务不是重新分析，而是**质量把关和纠错引导**：

1. **逻辑检查**：主Agent的推理链是否自洽？
   - 结论是否与数据匹配
   - 前后观点是否矛盾
   - 是否存在逻辑跳跃

2. **数据验证**：引用的数据是否准确？
   - 技术指标计算是否合理
   - 数据时效性是否明确
   - 是否误用历史数据

3. **风险补充**：主Agent遗漏的风险点
   - 未提及的重要风险
   - 过度乐观/悲观的倾向
   - 缺失的上下文信息

4. **提问引导**：帮助用户更好地使用系统
   - 建议补充哪些信息
   - 推荐进一步分析的角度

## 工作原则
- **保守**：宁可多问，不可漏掉风险
- **简洁**：只指出关键问题，不重复主Agent的内容
- **建设性**：提出问题时给出改进方向
- **尊重用户**：最终判断权在用户，不强加观点

## 输出格式
使用结构化格式输出：

🔍 快速检查：
[一句话总结主分析的质量]

发现 N 个需要注意的点：

1. ⚠️ [问题类型] [具体描述]
   💡 建议：[如何改进]

2. ❓ [问题类型] [具体描述]
   💡 建议：[如何改进]

...

✅ 分析中做得好的：[简要肯定]

👤 你认为这个分析：
[等待用户选择：合理 / 有问题需要纠正 / 继续提问]

## 问题类型标记
- ⚠️ 风险遗漏
- ❓ 逻辑疑问
- 📊 数据问题
- 💭 信息缺失
- ⏰ 时效性问题

## 示例

**主Agent分析**："贵州茅台RSI=32超卖，MACD金叉，建议低吸"

**你的评判**：
🔍 快速检查：
技术面分析基本合理，但风险提示不足。

发现 3 个需要注意的点：

1. ⚠️ 风险遗漏：虽然RSI超卖，但未检查成交量是否配合
   💡 建议：补充查询近5日成交量变化，确认是否有放量信号

2. ❓ 逻辑疑问：MACD金叉在哪个周期？日线金叉和60分钟金叉意义不同
   💡 建议：明确具体周期，或补充多周期共振分析

3. 💭 信息缺失：未提及茅台所处板块（白酒）近期走势
   💡 建议：可调用 sector_ranking 查看板块整体情况

✅ 分析中做得好的：
正确识别了超卖信号，指标计算准确。

👤 你认为这个分析：
"""


class JudgeAgent:
    """评判Agent - 负责质量把关和纠错引导"""

    def __init__(self, setting: dict = None):
        self.client = LLMClient(setting)
        self.setting = setting or self.client.setting

    async def judge_stream_async(self, main_conclusion: str, conversation_history: list):
        """流式评判主Agent的分析

        Args:
            main_conclusion: 主Agent的最终结论
            conversation_history: 完整对话历史（包含工具调用）

        Yields:
            (event_type, content) 元组
            event_type: "content" | "issues_found" | "done"
        """
        # 构建评判上下文
        context = self._build_judge_context(main_conclusion, conversation_history)

        messages = [{"role": "system", "content": JUDGE_SYSTEM_PROMPT}, {"role": "user", "content": context}]

        # 流式调用LLM
        content_buffer = ""
        issue_count = 0

        async for chunk in self.client.chat_stream_async(messages, tools=None):
            if chunk.type == "content":
                content_buffer += chunk.text
                yield ("content", chunk.text)

                # 实时统计问题数量（检测数字开头的行）
                if chunk.text.strip() and any(chunk.text.strip().startswith(f"{i}.") for i in range(1, 10)):
                    issue_count += 1
                    yield (
                        "issues_found",
                        json.dumps({"count": issue_count, "partial": content_buffer}, ensure_ascii=False),
                    )

        yield ("done", "")

    def _build_judge_context(self, main_conclusion: str, conversation_history: list) -> str:
        """构建评判上下文"""
        # 提取用户原始问题
        user_query = ""
        for msg in conversation_history:
            if msg["role"] == "user":
                user_query = msg["content"]
                break

        # 提取工具调用记录
        tool_calls = []
        for msg in conversation_history:
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    # 安全获取参数
                    tool_name = tc.get("name", "unknown")
                    tool_args = tc.get("arguments", {})
                    args_str = json.dumps(tool_args, ensure_ascii=False)
                    tool_calls.append(f"{tool_name}({args_str})")

        # 构建上下文
        tool_list = "\n".join(["- " + tc for tc in tool_calls]) if tool_calls else "（无工具调用）"

        context = f"""请评判以下分析：

**用户问题**：{user_query}

**主Agent调用的工具**：
{tool_list}

**主Agent的最终分析**：
{main_conclusion}

---

请按照你的职责进行评判，输出结构化的检查结果。
"""
        return context
