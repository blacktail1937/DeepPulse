"""DeepPulse TUI主应用"""

import asyncio
import json

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input

from agent.agent import StockAgent
from agent.judge_agent import JudgeAgent
from agent.tui.widgets import (
    ChatLog,
    DataPanel,
    ToolPanel,
)


class DeepPulseTUI(App):
    """DeepPulse TUI主应用"""

    TITLE = "DeepPulse - AI股票分析助手"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", key_display="^Q"),
        Binding("ctrl+r", "reset", "重置对话", key_display="^R"),
        Binding("ctrl+l", "clear_screen", "清屏", key_display="^L"),
    ]

    def __init__(self, setting: dict = None, verbose: bool = False):
        super().__init__()
        self.setting = setting
        self.verbose = verbose
        self.agent = None
        self.judge_agent = None
        self.judge_result = None
        self.current_query = ""

    def compose(self) -> ComposeResult:
        """构建界面布局（两栏布局：对话流 + 工具面板）"""
        yield Header()

        with Horizontal(id="main-container"):
            # 左侧：对话流（主要区域）
            with Vertical(id="chat-panel"):
                yield ChatLog(id="chat-log")
                yield Input(id="chat-input", placeholder="输入你的问题... (Ctrl+Q 退出)")

            # 右侧面板：工具执行 + 数据
            with Vertical(id="right-panel"):
                yield ToolPanel()
                yield DataPanel()

        yield Footer()

    async def on_mount(self) -> None:
        """启动时初始化"""
        self.chat_log = self.query_one("#chat-log", ChatLog)
        self.chat_input = self.query_one("#chat-input", Input)
        self.tool_panel = self.query_one(ToolPanel)
        self.data_panel = self.query_one(DataPanel)

        # 显示欢迎消息
        self.chat_log.add_system_message("✨ 欢迎使用 DeepPulse v0.2.0！\n⏳ 正在后台初始化 Agent，请稍候...")

        # 聚焦输入框
        self.chat_input.focus()

        # 异步初始化Agent（不阻塞UI）
        asyncio.create_task(self._init_agents_async())

    async def _init_agents_async(self):
        """异步初始化Agent（后台执行，不阻塞UI）"""
        try:
            # 在线程池中执行（避免阻塞事件循环）
            loop = asyncio.get_event_loop()

            # 初始化主Agent
            self.agent = await loop.run_in_executor(
                None, lambda: StockAgent(setting=self.setting, verbose=self.verbose)
            )

            # 初始化评判Agent
            self.judge_agent = await loop.run_in_executor(None, lambda: JudgeAgent(setting=self.setting))

            # 初始化完成提示
            self.chat_log.add_system_message(
                "✅ Agent 初始化完成！现在可以开始提问。\n"
                "💡 提示：输入「评判一下」或「帮我看看」可以让评判Agent检查分析质量。"
            )

        except Exception as e:
            self.chat_log.add_system_message(f"❌ Agent 初始化失败: {str(e)}")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理用户输入"""
        if event.input.id != "chat-input":
            return

        query = event.value.strip()
        if not query:
            return

        # 清空输入框
        event.input.value = ""

        # 处理特殊命令
        if query in ["quit", "exit", "q"]:
            self.exit()
            return
        elif query == "reset":
            await self.action_reset()
            return
        elif query.startswith("/"):
            await self.handle_command(query)
            return

        # 检查Agent是否已初始化
        if self.agent is None:
            self.chat_log.add_system_message("⏳ Agent 正在初始化中，请稍候...")
            return

        # 保存当前查询
        self.current_query = query

        # 显示用户消息
        self.chat_log.add_user_message(query)

        # 检测是否是评判命令
        judge_triggers = ["评判", "评判一下", "帮我看看", "检查一下", "有问题吗", "对吗", "对不对"]
        is_judge_request = any(trigger in query for trigger in judge_triggers)

        if is_judge_request and self.agent and len(self.agent.messages) > 2:
            # 用户请求评判，检查是否有内容可以评判
            last_msg = self.agent.messages[-1]
            if last_msg.get("role") == "assistant" and last_msg.get("content"):
                # 有助手回复内容，启动评判Agent
                await self.run_judge_agent()
            else:
                # 没有内容可评判
                self.chat_log.add_system_message("⚠️ 没有可以评判的内容，请先进行分析")
                self.chat_input.focus()
        else:
            # 正常分析流程
            await self.run_main_agent(query)

    async def run_main_agent(self, query: str):
        """运行主分析Agent（流式输出）"""
        # 创建主Agent消息容器
        main_container = self.chat_log.add_agent_container("🤔 主分析")

        thinking_buffer = ""
        content_buffer = ""

        try:
            async for event_type, text in self.agent.chat_stream_async(query):
                if event_type == "round":
                    main_container.update_status(f"Round {text}")

                elif event_type == "thinking":
                    thinking_buffer += text
                    main_container.update_thinking(thinking_buffer)

                elif event_type == "content":
                    content_buffer += text
                    main_container.update_content(content_buffer)

                elif event_type == "tool_start":
                    tool_name, tool_args = self.parse_tool_call(text)
                    self.tool_panel.add_tool_execution(tool_name, tool_args)
                    main_container.add_tool_badge(tool_name)

                    # 更新数据面板
                    if tool_name == "realtime_price":
                        self.data_panel.update_data("查询", tool_args.get("code", ""))

                elif event_type == "tool_result":
                    self.tool_panel.complete_tool_execution(text)

                    # 尝试解析工具结果更新数据面板
                    try:
                        result = json.loads(text)
                        if "price" in result:
                            self.data_panel.update_data("当前价", str(result["price"]))
                        if "change_pct" in result:
                            self.data_panel.update_data("涨跌幅", str(result["change_pct"]))
                    except Exception:
                        pass

                elif event_type == "done":
                    main_container.mark_complete()
                    break

        except Exception as e:
            main_container.update_content(f"❌ 错误: {str(e)}")
            main_container.mark_complete()

    async def run_judge_agent(self):
        """运行评判Agent（流式输出）"""
        # 获取主Agent的最终结论
        if not self.agent.messages or len(self.agent.messages) < 2:
            return

        main_conclusion = self.agent.messages[-1].get("content", "")
        if not main_conclusion:
            return

        # 创建评判Agent容器
        judge_container = self.chat_log.add_agent_container("⚖️ 评判Agent")
        judge_container.update_status("正在检查分析质量...")

        content_buffer = ""
        issues = []

        try:
            async for event_type, text in self.judge_agent.judge_stream_async(main_conclusion, self.agent.messages):
                if event_type == "content":
                    content_buffer += text
                    judge_container.update_content(content_buffer)

                elif event_type == "issues_found":
                    data = json.loads(text)
                    issue_count = data.get("count", 0)
                    judge_container.update_status(f"发现 {issue_count} 个需要注意的点")

                elif event_type == "done":
                    judge_container.mark_complete()
                    break

        except Exception as e:
            judge_container.update_content(f"❌ 评判出错: {str(e)}")
            judge_container.mark_complete()

        # 保存评判结果
        self.judge_result = {"content": content_buffer, "issues": issues}

        # 显示用户确认对话框
        self.show_confirmation_dialog()

    def show_confirmation_dialog(self):
        """显示用户确认对话框（简化版：只有认可/不认可）"""
        self.chat_log.add_confirmation_buttons([("✅ 认可", "accept"), ("❌ 不认可", "reject")])

    async def on_button_pressed(self, event) -> None:
        """处理按钮点击"""
        button_id = event.button.id

        if button_id == "confirm-accept":
            # 用户认可，自动学习记录
            await self.handle_accept()

        elif button_id == "confirm-reject":
            # 用户不认可，不记录
            self.chat_log.add_system_message("✅ 已忽略此次评判")
            self.chat_input.focus()

    async def handle_accept(self):
        """处理用户认可（自动学习记录）"""
        if not self.judge_result or not self.judge_result.get("content"):
            self.chat_log.add_system_message("⚠️ 没有可记录的评判内容")
            self.chat_input.focus()
            return

        try:
            from agent.tools import TOOL_DISPATCH

            TOOL_DISPATCH["record_learning"](
                learned_what=f"用户认可评判Agent对「{self.current_query[:50]}...」的检查意见",
                learned_why="评判Agent发现了主分析中的潜在问题或改进点",
                apply_when="在进行类似分析时参考这些检查点",
                category="user_correction",
                importance=0.7,
            )
            self.chat_log.add_system_message("✅ 已记录评判内容到学习记忆")
        except Exception as e:
            self.chat_log.add_system_message(f"⚠️ 记录失败: {str(e)}")

        self.chat_input.focus()

    async def show_memory(self):
        """显示记忆"""
        try:
            from agent.tools import TOOL_DISPATCH

            result = TOOL_DISPATCH["list_memories"](limit=10)
            self.chat_log.add_system_message(f"🧠 最近记忆：\n{result}")
        except Exception as e:
            self.chat_log.add_system_message(f"⚠️ 获取失败: {str(e)}")

    def parse_tool_call(self, text: str) -> tuple:
        """解析工具调用字符串"""
        # text format: "tool_name({...})"
        try:
            idx = text.index("(")
            tool_name = text[:idx]
            args_str = text[idx + 1 : -1]
            tool_args = json.loads(args_str) if args_str else {}
            return tool_name, tool_args
        except Exception:
            return text, {}

    async def action_reset(self) -> None:
        """重置对话"""
        if self.agent:
            self.agent.reset()
        self.chat_log.clear()
        self.data_panel.clear_data()
        self.tool_panel.completed.clear()
        self.chat_log.add_system_message("🔄 对话已重置")
        self.chat_input.focus()

    async def action_clear_screen(self) -> None:
        """清屏"""
        self.chat_log.clear()
        self.chat_input.focus()


def run_tui(setting: dict = None, verbose: bool = False):
    """启动TUI应用"""
    app = DeepPulseTUI(setting=setting, verbose=verbose)
    app.run()
