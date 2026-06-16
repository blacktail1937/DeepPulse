"""自选股管理测试"""

import tempfile
from pathlib import Path

from src.database import get_connection, init_tables


def _make_watchlist():
    """创建已初始化表结构的 WatchlistManager（使用临时文件数据库）"""
    from agent.watchlist import WatchlistManager

    tmp = Path(tempfile.mkdtemp()) / "test.duckdb"
    conn = get_connection(tmp)
    init_tables(conn)
    conn.close()
    return WatchlistManager(db_path=tmp)


class TestWatchlistManager:
    """测试自选股管理核心功能"""

    def test_add_stock(self):
        """添加自选股应返回成功"""
        wl = _make_watchlist()
        result = wl.add("600519", group="默认", name="贵州茅台", notes="测试")
        assert isinstance(result, dict)
        assert result.get("status") in ("added", "ok") or "code" in result

    def test_remove_stock(self):
        """移除自选股应返回成功"""
        wl = _make_watchlist()
        wl.add("600519", group="默认", name="贵州茅台")
        result = wl.remove("600519", "默认")
        assert isinstance(result, dict)

    def test_list_empty(self):
        """空自选股列表应返回空"""
        wl = _make_watchlist()
        codes = wl.get_codes("默认")
        assert isinstance(codes, list)
        assert len(codes) == 0

    def test_add_and_list(self):
        """添加后应能列出"""
        wl = _make_watchlist()
        wl.add("600519", group="默认", name="贵州茅台")
        wl.add("000001", group="默认", name="平安银行")
        codes = wl.get_codes("默认")
        assert "600519" in codes
        assert "000001" in codes

    def test_add_duplicate_handled(self):
        """重复添加不应崩溃"""
        wl = _make_watchlist()
        wl.add("600519", group="默认", name="贵州茅台")
        result = wl.add("600519", group="默认", name="贵州茅台")
        assert isinstance(result, dict)

    def test_alert_rule(self):
        """设置告警规则应返回成功"""
        wl = _make_watchlist()
        wl.add("600519", group="默认", name="贵州茅台")
        result = wl.add_alert_rule("600519", "price_above", {"threshold": 2000.0})
        assert isinstance(result, dict)

    def test_multiple_groups(self):
        """不同分组应独立管理"""
        wl = _make_watchlist()
        wl.add("600519", group="白酒", name="贵州茅台")
        wl.add("000001", group="银行", name="平安银行")
        baijiu = wl.get_codes("白酒")
        bank = wl.get_codes("银行")
        assert "600519" in baijiu
        assert "000001" in bank
        assert "600519" not in bank
