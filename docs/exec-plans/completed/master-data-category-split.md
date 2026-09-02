# 主檔分類拆分

Plan status: completed

## 目的

將供應商主檔與產品主檔拆成四個固定 scope 側欄頁，遷移 `suppliers.category` 術語，新增 `products.item_category`，並同步 NCR／供應商事件 workflow 篩選。

## 驗證

- `tests.test_master_data_category_split`
- `ncr.tests.test_supplier_sync`
- `tests.test_master_data_safety_confirmations`
- `tests.test_top_nav_compact_height`
