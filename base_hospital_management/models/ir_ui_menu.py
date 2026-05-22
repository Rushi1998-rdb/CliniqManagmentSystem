from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible_ids = set(super()._visible_menu_ids(debug=debug))
        hidden_menu_ids = self._get_hidden_menu_ids_for_user()
        return visible_ids - hidden_menu_ids

    def _get_hidden_menu_ids_for_user(self):
        user = self.env.user
        hidden_roots = []

        if user.has_group(
            "base_hospital_management.base_hospital_management_group_hide_home_menus"
        ):
            hidden_roots.extend(
                [
                    "mail.menu_root_discuss",
                    "sale.sale_menu_root",
                    "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
                    "account.menu_finance",
                    "website.menu_website_configuration",
                    "utm.menu_link_tracker_root",
                ]
            )

        if user.has_group(
            "base_hospital_management.base_hospital_management_group_hide_employee_home_menu"
        ):
            hidden_roots.append("hr.menu_hr_root")

        if user.has_group(
            "base_hospital_management.base_hospital_management_group_hide_apps_home_menu"
        ):
            hidden_roots.extend(
                [
                    "base.menu_management",
                    "base.menu_apps",
                ]
            )

        if user.has_group(
            "base_hospital_management.base_hospital_management_group_hide_settings_home_menu"
        ):
            hidden_roots.extend(
                [
                    "base.menu_administration",
                ]
            )

        hidden_roots = [
            xmlid for xmlid in hidden_roots
            if xmlid != "stock.menu_stock_root"
        ]

        hidden_root_ids = []
        for xmlid in hidden_roots:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                hidden_root_ids.append(menu.id)

        if not hidden_root_ids:
            return set()

        hidden_menus = self.with_context(
            active_test=False,
            **{"ir.ui.menu.full_list": True},
        ).sudo().search(
            [("id", "child_of", hidden_root_ids)]
        )
        return set(hidden_menus.ids)
