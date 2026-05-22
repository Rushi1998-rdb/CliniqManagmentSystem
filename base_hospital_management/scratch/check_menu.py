
import odoo
from odoo import api, SUPERUSER_ID

def check_vendors_menu():
    registry = odoo.registry('HMS_Test')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        # Search for the Vendors menu item
        menu = env['ir.ui.menu'].search([('name', 'ilike', 'Vendors')], limit=20)
        print("Vendors Menu Analysis:")
        for m in menu:
            action = m.action
            if action:
                print(f"Menu ID: {m.id}, Name: {m.complete_name}")
                print(f"  Action: {action.name} (ID: {action.id}, Model: {action._name}, XML_ID: {action.get_external_id().get(action.id)})")
                if hasattr(action, 'domain'):
                    print(f"  Domain: {action.domain}")

if __name__ == "__main__":
    check_vendors_menu()
