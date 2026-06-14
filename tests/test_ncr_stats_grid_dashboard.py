from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QScrollArea, QSizePolicy, QLabel
from PySide6.QtCharts import QChartView, QPieSlice

from ui.widgets.ncr_stats_widget import NcrStatsWidget
from ui.widgets.common_widgets import EmptyStateWidget


class NcrStatsGridDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self.widgets: list[NcrStatsWidget] = []

    def tearDown(self) -> None:
        for w in self.widgets:
            w.close()
        self.app.processEvents()

    def _build_widget(
        self,
        *,
        suppliers: list | None = None,
        products: list | None = None,
        scrap_rework: list | None = None,
        return_slips: list | None = None,
    ) -> NcrStatsWidget:
        # Mocking the service calls
        mock_sup = suppliers if suppliers is not None else []
        mock_prod = products if products is not None else []
        mock_sr = scrap_rework if scrap_rework is not None else []
        mock_rs = return_slips if return_slips is not None else []

        with (
            patch("ncr.services.stats_service.get_top_suppliers_stats_filtered", return_value=mock_sup),
            patch("ncr.services.stats_service.get_top_products_stats_filtered", return_value=mock_prod),
            patch("ncr.services.stats_service.get_scrap_rework_ratio_filtered", return_value=mock_sr),
            patch("ncr.services.stats_service.get_return_slip_ratio_filtered", return_value=mock_rs),
        ):
            widget = NcrStatsWidget(lazy_load=False)
            widget.show()
            self.app.processEvents()
            self.widgets.append(widget)
            return widget

    def test_ncr_stats_widget_has_scroll_area_and_grid_layout(self) -> None:
        # 提供非空數據以讓 4 個圖表顯示
        suppliers = [{"supplier_name": "A", "total_qty": 10}]
        products = [{"product_name": "P", "total_qty": 5}]
        scrap_rework = [{"disposition": "報廢", "total_qty": 20}]
        return_slips = [{"return_slip_type": "廠內退料", "total_qty": 60}]

        widget = self._build_widget(
            suppliers=suppliers,
            products=products,
            scrap_rework=scrap_rework,
            return_slips=return_slips,
        )
        
        # 應該有 QScrollArea 容器
        scroll_areas = widget.findChildren(QScrollArea)
        self.assertEqual(1, len(scroll_areas))
        scroll_area = scroll_areas[0]
        self.assertEqual("NcrStatsScrollArea", scroll_area.objectName())
        
        # 內建的 grid_layout 屬性必須是 QGridLayout
        grid_layout = widget.grid_layout
        self.assertIsInstance(grid_layout, QGridLayout)
        
        # 網格中必須有 4 個 QChartView 統計圖表
        chart_views = widget.findChildren(QChartView)
        self.assertEqual(4, len(chart_views))

    def test_grid_layout_stretch_and_chart_size_policies(self) -> None:
        # 提供非空數據
        suppliers = [{"supplier_name": "A", "total_qty": 10}]
        products = [{"product_name": "P", "total_qty": 5}]
        scrap_rework = [{"disposition": "報廢", "total_qty": 20}]
        return_slips = [{"return_slip_type": "廠內退料", "total_qty": 60}]

        widget = self._build_widget(
            suppliers=suppliers,
            products=products,
            scrap_rework=scrap_rework,
            return_slips=return_slips,
        )
        grid_layout = widget.grid_layout
        
        # 驗證行與列的 Stretch 權重，確保 2x2 鋪滿不塌陷
        self.assertEqual(1, grid_layout.rowStretch(0))
        self.assertEqual(1, grid_layout.rowStretch(1))
        
        # 驗證 columns 的 stretch
        self.assertEqual(1, grid_layout.columnStretch(0))
        self.assertEqual(1, grid_layout.columnStretch(1))
        
        # 驗證每個圖表 view 的 size policy 均為 Expanding
        chart_views = widget.findChildren(QChartView)
        for view in chart_views:
            self.assertEqual(QSizePolicy.Policy.Expanding, view.sizePolicy().horizontalPolicy())
            self.assertEqual(QSizePolicy.Policy.Expanding, view.sizePolicy().verticalPolicy())

    def test_donut_chart_uses_qpieslice_label_outside(self) -> None:
        scrap_rework = [
            {"disposition": "報廢", "total_qty": 20},
            {"disposition": "重工", "total_qty": 10},
        ]
        # 提供其他必要數據以避免 empty state
        suppliers = [{"supplier_name": "A", "total_qty": 10}]
        products = [{"product_name": "P", "total_qty": 5}]
        return_slips = [{"return_slip_type": "廠內退料", "total_qty": 60}]

        widget = self._build_widget(
            suppliers=suppliers,
            products=products,
            scrap_rework=scrap_rework,
            return_slips=return_slips,
        )
        
        chart_views = widget.findChildren(QChartView)
        
        # 尋找 "報廢 / 重工 比例佔比" Donut Chart 並驗證 QPieSlice 的 label position
        donut_chart_view = None
        for view in chart_views:
            if "報廢 / 重工" in view.chart().title():
                donut_chart_view = view
                break
        
        self.assertIsNotNone(donut_chart_view)
        assert donut_chart_view is not None
        
        series_list = donut_chart_view.chart().series()
        self.assertEqual(1, len(series_list))
        series = series_list[0]
        
        slices = series.slices()
        self.assertEqual(2, len(slices))
        for slice_obj in slices:
            self.assertTrue(slice_obj.isLabelVisible())
            # 確保 label 顯示在外面以避免重疊
            self.assertEqual(QPieSlice.LabelPosition.LabelOutside, slice_obj.labelPosition())

    def test_all_time_checkbox_signal_blocking(self) -> None:
        widget = self._build_widget()
        
        # 測試切換 "全期資料"
        checkbox = widget.all_time_toggle
        month_edit = widget.month_input
        
        # 設置 mock 刷新函式
        with patch.object(widget, "refresh_data") as mock_refresh:
            # 勾選 "全期資料"
            checkbox.setChecked(True)
            self.app.processEvents()
            
            # month_edit 應該會被 disable
            self.assertFalse(month_edit.isEnabled())
            # 必須調用一次 refresh_data
            mock_refresh.assert_called_once()
            
            mock_refresh.reset_mock()
            
            # 取消勾選 "全期資料"
            checkbox.setChecked(False)
            self.app.processEvents()
            
            # month_edit 應該恢復啟用
            self.assertTrue(month_edit.isEnabled())
            # 必須調用一次 refresh_data
            mock_refresh.assert_called_once()

    def test_insights_generation_with_empty_and_normal_data(self) -> None:
        # 1. 測試空數據
        widget = self._build_widget()
        self.assertIn("暫無可用數據以生成管理建議", widget.insight_label.text())
        
        # 2. 測試正常數據
        suppliers = [
            {"supplier_name": "供應商A", "case_count": 5, "total_qty": 50},
            {"supplier_name": "供應商B", "case_count": 3, "total_qty": 30},
        ]
        products = [
            {"product_name": "產品X", "case_count": 4, "total_qty": 40},
        ]
        scrap_rework = [
            {"disposition": "報廢", "case_count": 5, "total_qty": 50},
            {"disposition": "重工", "case_count": 3, "total_qty": 30},
        ]
        return_slips = [
            {"return_slip_type": "廠內退料", "case_count": 6, "total_qty": 60},
        ]
        
        widget_with_data = self._build_widget(
            suppliers=suppliers,
            products=products,
            scrap_rework=scrap_rework,
            return_slips=return_slips,
        )
        insights = widget_with_data.insight_label.text()
        self.assertIn("供應商A", insights)
        self.assertIn("產品X", insights)
        self.assertIn("報廢", insights)
        self.assertIn("廠內退料", insights)


if __name__ == "__main__":
    unittest.main()
