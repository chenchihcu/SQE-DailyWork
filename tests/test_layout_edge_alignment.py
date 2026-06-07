from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollArea, QWidget

from ui.main_window import MainWindow
from ui.theme import apply_app_theme


class LayoutEdgeAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def setUp(self) -> None:
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()

    def _top_level_subpanels(self, page: QWidget) -> list[QFrame]:
        return [
            frame
            for frame in page.findChildren(QFrame)
            if frame.parentWidget() is page and frame.property("role") == "subpanel"
        ]

    def _root_margin_frames(self, page: QWidget) -> list[QFrame]:
        scroll_area = page.findChild(QScrollArea, "HomeScrollArea")
        if scroll_area is not None:
            self.assertIs(scroll_area.parentWidget(), page)
            self.assertEqual((0, 0), (scroll_area.geometry().x(), scroll_area.geometry().y()))
            content = scroll_area.widget()
            self.assertIsNotNone(content)
            assert content is not None
            self.assertEqual("HomeContent", content.objectName())
            return [
                frame
                for frame in content.findChildren(QFrame)
                if frame.parentWidget() is content
            ]

        return [
            frame
            for frame in page.findChildren(QFrame)
            if frame.parentWidget() is page
            and frame.property("role") in ("panel", "subpanel")
        ]

    def _find_label(self, page: QWidget, text: str) -> QLabel:
        for label in page.findChildren(QLabel):
            if label.text() == text:
                return label
        self.fail(f"label not found: {text}")

    def _find_button(self, page: QWidget, text: str) -> QPushButton:
        for button in page.findChildren(QPushButton):
            if button.text() == text:
                return button
        self.fail(f"button not found: {text}")

    def test_stack_fills_content_host_without_outer_margin(self) -> None:
        from ui.page_header_bar import PageHeaderBar
        stack = self.window.stack
        content_host = stack.parentWidget()
        self.assertIsNotNone(content_host)
        assert content_host is not None

        # Content host is ContentHost QFrame; it contains PageHeaderBar + stack.
        # Verify no extra horizontal margin on the stack.
        self.assertEqual(0, stack.geometry().x())
        self.assertEqual(stack.width(), content_host.contentsRect().width())

        # Stack starts below PageHeaderBar — verify y offset matches header height.
        header_bar = self.window._header_bar
        self.assertIsInstance(header_bar, PageHeaderBar)
        self.assertGreater(stack.geometry().y(), 0)
        self.assertEqual(stack.geometry().y(), header_bar.height())

    def test_primary_pages_have_no_extra_root_margins(self) -> None:
        pages: list[QWidget] = [
            self.window.home_widget,
            self.window.entry_widget,
            self.window.events_widget,
            self.window.stats_widget,
            self.window.master_widget,
        ]

        for page in pages:
            self.window.stack.setCurrentWidget(page)
            self.app.processEvents()

            top_level_frames = self._root_margin_frames(page)
            self.assertGreater(len(top_level_frames), 0)

            min_x = min(frame.geometry().x() for frame in top_level_frames)
            min_y = min(frame.geometry().y() for frame in top_level_frames)
            self.assertEqual(0, min_x)
            self.assertEqual(0, min_y)

    def test_event_management_has_single_top_level_control_subpanel(self) -> None:
        page = self.window.events_widget
        self.window.stack.setCurrentWidget(page)
        self.app.processEvents()
        self.assertEqual(1, len(self._top_level_subpanels(page)))

    def test_event_management_filter_row_keeps_actions_without_overlap_at_min_width(self) -> None:
        """事件管理篩選列：篩選控制項同列不重疊（新增按鈕已移至工具列列）。"""
        self.window.resize(1100, 740)
        self.window.stack.setCurrentWidget(self.window.events_widget)
        self.app.processEvents()

        page = self.window.events_widget
        control_panel = self._top_level_subpanels(page)[0]
        controls = [
            self._find_label(page, "供應商"),
            page.supplier_filter_input,
            self._find_label(page, "狀態"),
            page.status_combo,
            self._find_button(page, "查詢"),
            self._find_button(page, "清除條件"),
        ]

        rects = [widget.geometry() for widget in controls]
        for widget in controls:
            self.assertIs(widget.parentWidget(), control_panel)

        sorted_rects = sorted(rects, key=lambda rect: rect.x())
        for left, right in zip(sorted_rects, sorted_rects[1:]):
            self.assertLess(left.right(), right.left())

        center_ys = [rect.center().y() for rect in rects]
        self.assertLessEqual(max(center_ys) - min(center_ys), 2)

        # New-event actions remain available on the consolidated page (toolbar row).
        self.assertIsNotNone(self._find_button(page, "新增訪廠"))
        self.assertIsNotNone(self._find_button(page, "新增異常"))

    def test_event_management_keeps_pagination_control_contract(self) -> None:
        """事件管理保留既有分頁列尺寸。"""
        self.window.stack.setCurrentWidget(self.window.events_widget)
        self.app.processEvents()
        query_combo_w = self.window.events_widget.pagination.page_size_combo.width()

        self.assertEqual(84, query_combo_w)

    def test_master_inline_toolbar_uses_single_row_with_left_query(self) -> None:
        self.window.resize(1100, 740)
        self.window._open_master_data()
        self.app.processEvents()

        page = self.window.master_widget
        toolbar = page.inline_toolbar
        self.assertIsNotNone(toolbar)
        assert toolbar is not None
        self.assertEqual("MasterInlineToolbar", toolbar.objectName())

        primary_row = toolbar.findChild(QWidget, "MasterPrimaryRow")
        query_row = toolbar.findChild(QWidget, "MasterQueryRow")
        self.assertIsNotNone(primary_row)
        assert primary_row is not None
        self.assertIsNone(query_row)

        controls = [
            page.btn_supplier_create,
            page.btn_supplier_update,
            page.btn_supplier_toggle,
            page.btn_supplier_delete,
            page.btn_supplier_delete_selected,
            page.btn_supplier_filter,
            page.btn_supplier_clear,
        ]

        local_rects: list[tuple[int, int, int, int]] = []
        for widget in controls:
            self.assertTrue(widget.isVisible())
            self.assertGreater(widget.width(), 0)
            top_left = widget.mapTo(primary_row, widget.rect().topLeft())
            local_rects.append((top_left.x(), top_left.y(), widget.width(), widget.height()))

        sorted_rects = sorted(local_rects, key=lambda item: item[0])
        for left, right in zip(sorted_rects, sorted_rects[1:]):
            self.assertLess(left[0] + left[2] - 1, right[0])

        center_ys = [top + (height // 2) for _x, top, _width, height in local_rects]
        self.assertLessEqual(max(center_ys) - min(center_ys), 3)

        self.assertTrue(page.query_input.isVisible())
        self.assertGreater(page.query_input.width(), 0)
        query_top_left = page.query_input.mapTo(primary_row, page.query_input.rect().topLeft())
        query_right = query_top_left.x() + page.query_input.width()
        self.assertLessEqual(query_top_left.x(), 2)
        self.assertLess(query_right, primary_row.width())

        action_top_left = page.action_stack.mapTo(primary_row, page.action_stack.rect().topLeft())
        action_right = action_top_left.x() + page.action_stack.width()
        self.assertLessEqual(primary_row.width() - action_right, 2)


if __name__ == "__main__":
    unittest.main()
