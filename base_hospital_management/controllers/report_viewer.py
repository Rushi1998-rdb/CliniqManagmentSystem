from odoo import http
from odoo.http import request


class HospitalReportViewer(http.Controller):
    """Render report PDFs inside a lightweight viewer page."""

    _ALLOWED_REPORTS = {
        "sale.report_saleorder": "Bill",
        "account.report_invoice": "Invoice",
    }

    @http.route(
        "/hospital/report/view/<string:report_name>/<int:doc_id>",
        type="http",
        auth="user",
    )
    def hospital_report_viewer(self, report_name, doc_id, **kwargs):
        """Open a report in a tab with a custom favicon."""
        if report_name not in self._ALLOWED_REPORTS:
            return request.not_found()

        values = {
            "title": self._ALLOWED_REPORTS[report_name],
            "pdf_url": f"/report/pdf/{report_name}/{doc_id}",
            "favicon_url": "/base_hospital_management/static/description/icon.png",
        }
        return request.render("base_hospital_management.report_viewer_page", values)
