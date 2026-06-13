"""TUI界面核心组件"""

import time

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.containers import Container, ScrollableContainer
from textual.widgets import Button, Static


class ChatLog(ScrollableContainer):
    """对话流容器（自动滚动）"""

    DEFAULT_CSS = """
    ChatLog {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    """

    def add_user_message(self, text: str):
        """添加用户消息"""
        widget = Static()
        widget.update(Panel(Markdown(text), title="👤 你", border_style="cyan", padding=(0, 1)))
        self.mount(widget)
        self.scroll_end(animate=False)

    def add_agent_container(self, agent_name: str) -> "AgentMessageContainer":
        """添加Agent消息容器（支持流式更新）"""
        container = AgentMessageContainer(agent_name)
        self.mount(container)
        self.scroll_end(animate=False)
        return container

    def add_system_message(self, text: str):
        """添加系统消息"""
        widget = Static()
        widget.update(Panel(text, border_style="dim", padding=(0, 1)))
        self.mount(widget)
        self.scroll_end(animate=False)

    def add_confirmation_buttons(self, buttons: list):
        """添加确认按钮组"""
        button_group = ConfirmationButtons(buttons)
        self.mount(button_group)
        self.scroll_end(animate=False)


class AgentMessageContainer(Static):
    """Agent消息容器（支持流式更新）"""

    DEFAULT_CSS = """
    AgentMessageContainer {
        margin: 1 0;
    }
    """

    def __init__(self, agent_name: str):
        super().__init__()
        self.agent_name = agent_name
        self.thinking_text = ""
        self.content_text = ""
        self.tools = []
        self.status = ""
        self.complete = False

    def update_thinking(self, text: str):
        """更新思考过程"""
        self.thinking_text = text
        self.refresh_display()

    def update_content(self, text: str):
        """更新输出内容"""
        self.content_text = text
        self.refresh_display()

    def add_tool_badge(self, tool_name: str):
        """添加工具调用徽章"""
        self.tools.append(tool_name)
        self.refresh_display()

    def update_status(self, status: str):
        """更新状态"""
        self.status = status
        self.refresh_display()

    def mark_complete(self):
        """标记完成"""
        self.complete = True
        self.refresh_display()

    def refresh_display(self):
        """刷新显示内容"""
        from rich.console import Group

        parts = []

        # 思考过程（折叠显示）
        if self.thinking_text and len(self.thinking_text) > 20:
            parts.append(Text(f"💭 {self.thinking_text[:80]}...", style="dim"))

        # 工具调用徽章
        if self.tools:
            tool_badges = " ".join([f"[🔧 {t}]" for t in self.tools[-5:]])  # 只显示最近5个
            parts.append(Text(tool_badges, style="yellow"))

        # 输出内容（Markdown渲染）
        if self.content_text:
            parts.append(Markdown(self.content_text))

        # 状态指示（流式输出时显示光标）
        if not self.complete and self.content_text:
            parts.append(Text("▊", style="blink"))

        content = Group(*parts) if parts else Text("...")

        title = f"{self.agent_name}"
        if self.status:
            title += f" - {self.status}"

        self.update(Panel(content, title=title, border_style="green" if self.complete else "yellow", padding=(0, 1)))

        # 触发父容器滚动
        if hasattr(self.parent, "scroll_end"):
            self.parent.scroll_end(animate=False)


class ToolPanel(Static):
    """工具执行面板"""

    DEFAULT_CSS = """
    ToolPanel {
        height: 15;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.executing = []  # 正在执行
        self.completed = []  # 已完成
        self.refresh_display()

    def add_tool_execution(self, tool_name: str, args: dict):
        """添加工具执行"""
        self.executing.append({"name": tool_name, "args": args, "start": time.time()})
        self.refresh_display()

    def complete_tool_execution(self, result: str):
        """完成工具执行"""
        if self.executing:
            tool = self.executing.pop(0)
            tool["duration"] = time.time() - tool["start"]
            tool["result"] = result[:100]
            self.completed.append(tool)
            # 只保留最近20个
            if len(self.completed) > 20:
                self.completed = self.completed[-20:]
            self.refresh_display()

    def refresh_display(self):
        """刷新显示"""
        from rich.console import Group
        from rich.text import Text

        lines = []

        # 正在执行
        if self.executing:
            lines.append(Text("🔄 正在执行:", style="yellow bold"))
            for tool in self.executing:
                lines.append(Text(f"  • {tool['name']}", style="yellow"))
        else:
            lines.append(Text("⏸ 空闲", style="dim"))

        lines.append(Text(""))

        # 已完成（最近5个）
        if self.completed:
            lines.append(Text("✅ 已完成:", style="green bold"))
            for tool in self.completed[-5:]:
                lines.append(Text(f"  • {tool['name']} ({tool['duration']:.1f}s)", style="green"))

        content = Group(*lines)
        self.update(Panel(content, title="🔧 工具面板", border_style="blue"))


class DataPanel(Static):
    """数据摘要面板"""

    DEFAULT_CSS = """
    DataPanel {
        height: 12;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.data = {}
        self.refresh_display()

    def update_data(self, key: str, value: str):
        """更新数据"""
        self.data[key] = value
        self.refresh_display()

    def clear_data(self):
        """清空数据"""
        self.data = {}
        self.refresh_display()

    def refresh_display(self):
        """刷新显示"""
        from rich.console import Group
        from rich.text import Text

        lines = []
        if self.data:
            for key, value in self.data.items():
                lines.append(Text(f"{key}: {value}", style="cyan"))
        else:
            lines.append(Text("暂无数据", style="dim"))

        content = Group(*lines)
        self.update(Panel(content, title="📊 数据摘要", border_style="blue"))


class WatchlistPanel(Static):
    """自选股面板"""

    DEFAULT_CSS = """
    WatchlistPanel {
        height: 12;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.stocks = []
        self.refresh_display()

    def set_stocks(self, stocks: list):
        """设置自选股列表"""
        self.stocks = stocks
        self.refresh_display()

    def refresh_display(self):
        """刷新显示"""
        from rich.console import Group
        from rich.text import Text

        lines = []
        if self.stocks:
            for stock in self.stocks[:8]:  # 最多显示8个
                code = stock.get("code", "")
                name = stock.get("name", "")
                price = stock.get("price", "")
                change = stock.get("change", "0")

                # 根据涨跌设置颜色
                try:
                    change_val = float(change.strip("%"))
                    if change_val > 0:
                        style = "red"
                        symbol = "●"
                    elif change_val < 0:
                        style = "green"
                        symbol = "●"
                    else:
                        style = "white"
                        symbol = "○"
                except Exception:
                    style = "white"
                    symbol = "○"

                lines.append(Text(f"{symbol} {code} {name}", style=style))
                lines.append(Text(f"   {price}  {change}", style=style))
        else:
            lines.append(Text("暂无自选股", style="dim"))
            lines.append(Text("使用 /watchlist add <代码> 添加", style="dim"))

        content = Group(*lines)
        self.update(Panel(content, title="📊 自选股", border_style="magenta"))


class PortfolioPanel(Static):
    """持仓面板"""

    DEFAULT_CSS = """
    PortfolioPanel {
        height: 10;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.positions = []
        self.refresh_display()

    def set_positions(self, positions: list):
        """设置持仓列表"""
        self.positions = positions
        self.refresh_display()

    def refresh_display(self):
        """刷新显示"""
        from rich.console import Group
        from rich.text import Text

        lines = []
        if self.positions:
            for pos in self.positions[:5]:  # 最多显示5个
                code = pos.get("code", "")
                shares = pos.get("shares", 0)
                profit = pos.get("profit", 0)
                profit_pct = pos.get("profit_pct", 0)

                style = "red" if profit > 0 else "green" if profit < 0 else "white"

                lines.append(Text(f"{code} {shares}股", style="white"))
                lines.append(Text(f"  {profit:+.0f}元 ({profit_pct:+.1f}%)", style=style))
        else:
            lines.append(Text("暂无持仓", style="dim"))

        content = Group(*lines)
        self.update(Panel(content, title="💼 持仓", border_style="magenta"))


class MarketPanel(Static):
    """市场概况面板"""

    DEFAULT_CSS = """
    MarketPanel {
        height: 10;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.market_data = {}
        self.refresh_display()

    def update_market(self, data: dict):
        """更新市场数据"""
        self.market_data = data
        self.refresh_display()

    def refresh_display(self):
        """刷新显示"""
        from rich.console import Group
        from rich.text import Text

        lines = []
        if self.market_data:
            lines.append(Text(f"上涨: {self.market_data.get('up', 0)}", style="red"))
            lines.append(Text(f"下跌: {self.market_data.get('down', 0)}", style="green"))
            lines.append(Text(f"涨停: {self.market_data.get('limit_up', 0)}", style="red bold"))
            lines.append(Text(f"跌停: {self.market_data.get('limit_down', 0)}", style="green bold"))
            lines.append(Text(f"情绪: {self.market_data.get('sentiment', '未知')}", style="cyan"))
        else:
            lines.append(Text("加载中...", style="dim"))

        content = Group(*lines)
        self.update(Panel(content, title="📈 市场概况", border_style="blue"))


class ConfirmationButtons(Container):
    """确认按钮组"""

    DEFAULT_CSS = """
    ConfirmationButtons {
        height: auto;
        layout: horizontal;
        margin: 1 0;
    }

    ConfirmationButtons Button {
        margin: 0 1;
    }
    """

    def __init__(self, buttons: list):
        super().__init__()
        self.button_configs = buttons

    def compose(self):
        """构建按钮"""
        for label, action in self.button_configs:
            btn = Button(label, id=f"confirm-{action}", variant="primary" if action == "accept" else "default")
            yield btn
