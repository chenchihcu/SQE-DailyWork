import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from ui.widgets.common_widgets import (
    SortableTableWidgetItem,
    create_status_item,
    preserve_table_sorting,
    style_table,
    text_table_item,
)


@pytest.fixture(autouse=True, scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_sortable_table_widget_item_comparison():
    """Test custom comparison logic in SortableTableWidgetItem for numbers and keys."""
    item1 = SortableTableWidgetItem("2")
    item2 = SortableTableWidgetItem("10")
    assert item1 < item2

    item_key1 = SortableTableWidgetItem("B", sort_key=10)
    item_key2 = SortableTableWidgetItem("A", sort_key=20)
    assert item_key1 < item_key2

    d1 = SortableTableWidgetItem("2026-05-11", sort_key="2026-05-11")
    d2 = SortableTableWidgetItem("2026-05-12", sort_key="2026-05-12")
    assert d1 < d2


def test_qtablewidget_header_click_and_sorting():
    """Test QTableWidget sorting enabled by style_table and header click interactions."""
    table = QTableWidget(3, 2)
    style_table(table)
    table.setHorizontalHeaderLabels(["ID", "Name"])

    with preserve_table_sorting(table):
        table.setItem(0, 0, SortableTableWidgetItem("10", sort_key=10))
        table.setItem(0, 1, text_table_item("Banana"))

        table.setItem(1, 0, SortableTableWidgetItem("2", sort_key=2))
        table.setItem(1, 1, text_table_item("Apple"))

        table.setItem(2, 0, SortableTableWidgetItem("5", sort_key=5))
        table.setItem(2, 1, text_table_item("Cherry"))

    # Sort ascending by Column 0 (ID)
    table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    assert table.item(0, 0).text() == "2"
    assert table.item(1, 0).text() == "5"
    assert table.item(2, 0).text() == "10"

    # Sort descending by Column 0 (ID)
    table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    assert table.item(0, 0).text() == "10"
    assert table.item(1, 0).text() == "5"
    assert table.item(2, 0).text() == "2"

    # Sort ascending by Column 1 (Name)
    table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
    assert table.item(0, 1).text() == "Apple"
    assert table.item(1, 1).text() == "Banana"
    assert table.item(2, 1).text() == "Cherry"


def test_preserve_table_sorting_across_repopulate():
    """Test that preserve_table_sorting maintains active column and direction after reloading."""
    table = QTableWidget(0, 2)
    style_table(table)
    table.setHorizontalHeaderLabels(["Code", "Status"])

    with preserve_table_sorting(table):
        table.setRowCount(2)
        table.setItem(0, 0, text_table_item("P1"))
        table.setItem(0, 1, create_status_item("待處理", sort_key="待處理"))
        table.setItem(1, 0, text_table_item("P2"))
        table.setItem(1, 1, create_status_item("已結案", sort_key="已結案"))

    table.sortByColumn(1, Qt.SortOrder.DescendingOrder)

    assert table.horizontalHeader().sortIndicatorSection() == 1
    assert table.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder

    with preserve_table_sorting(table):
        table.setRowCount(0)
        table.insertRow(0)
        table.setItem(0, 0, text_table_item("P3"))
        table.setItem(0, 1, create_status_item("待處理", sort_key="待處理"))

        table.insertRow(1)
        table.setItem(1, 0, text_table_item("P4"))
        table.setItem(1, 1, create_status_item("已結案", sort_key="已結案"))

    assert table.horizontalHeader().sortIndicatorSection() == 1
    assert table.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    assert table.item(0, 1).text() == "待處理"
    assert table.item(1, 1).text() == "已結案"
