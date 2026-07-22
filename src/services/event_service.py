"""Service layer for v2 minimalist events workflow.

This module is now a backward-compatible shim. All public functions are
re-exported from sub-modules under ``services/event/``.

New code should import from the specific sub-module as needed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from database import repository
from database.connection import get_connection

# Re-export module-level constants
EVENT_SCOPE_VISIT_ONLY = repository.EVENT_SCOPE_VISIT_ONLY
EVENT_SCOPE_VISIT_WITH_ANOMALY = repository.EVENT_SCOPE_VISIT_WITH_ANOMALY
EVENT_SCOPE_ANOMALY_ONLY = repository.EVENT_SCOPE_ANOMALY_ONLY
EVENT_SCOPE_CLOSED_ONLY = repository.EVENT_SCOPE_CLOSED_ONLY

# ---------------------------------------------------------------------------
# Re-exports: supplier CRUD
# ---------------------------------------------------------------------------
from services.event._supplier_service import (  # noqa: E402, F401
    list_suppliers,
    create_supplier,
    update_supplier,
    set_supplier_active,
    delete_supplier,
    list_supplier_contacts,
    add_supplier_contact,
    delete_supplier_contact,
    set_primary_contact,
    delete_suppliers,
    list_active_suppliers,
)

# ---------------------------------------------------------------------------
# Re-exports: product CRUD
# ---------------------------------------------------------------------------
from services.event._product_service import (  # noqa: E402, F401
    list_products,
    create_product,
    update_product,
    set_product_active,
    delete_product,
    list_active_products_for_supplier,
    has_active_suppliers,
    list_product_stage_change_logs,
)

# ---------------------------------------------------------------------------
# Re-exports: anomaly CRUD
# ---------------------------------------------------------------------------
from services.event._anomaly_service import (  # noqa: E402, F401
    create_anomaly,
    create_anomaly_with_visit_link,
    get_anomaly_detail,
    update_anomaly,
    update_anomaly_link,
    delete_anomaly,
    preview_anomaly_no,
    get_latest_tech_transfer_for_supplier,
    get_latest_visit_for_supplier_on_date,
    close_anomaly,
    update_anomaly_closed_at,
    reopen_anomaly,
    resync_anomaly_snapshot,
)

# ---------------------------------------------------------------------------
# Re-exports: visit CRUD
# ---------------------------------------------------------------------------
from services.event._visit_service import (  # noqa: E402, F401
    create_visit,
    update_visit,
    get_visit_detail,
    delete_visit,
    list_visits_for_supplier,
    list_pending_visit_defect_notes,
    confirm_visit_defect_note_as_anomaly,
)

# ---------------------------------------------------------------------------
# Re-exports: event query / dashboard / statistics
# ---------------------------------------------------------------------------
from services.event._query_service import (  # noqa: E402, F401
    list_events,
    get_dashboard_summary,
    get_monthly_stats,
    get_responsible_person_stats,
    list_events_by_range,
    summarize_range_events,
    get_anomaly_category_pareto_by_range,
    get_responsible_person_stats_by_range,
    get_visit_trend_by_range,
    get_anomaly_trend_by_range,
    get_anomaly_closure_activity_by_range,
)

# ---------------------------------------------------------------------------
# Re-exports: PDF / Excel export
# ---------------------------------------------------------------------------
from services import event_pdf_exporter  # noqa: E402, F401

from services.event._export_service import (  # noqa: E402, F401
    default_event_pdf_filename,
    export_event_pdf,
    export_brief_event_pdf,
    render_brief_event_image,
    export_monthly_excel,
    export_events_report,
)

