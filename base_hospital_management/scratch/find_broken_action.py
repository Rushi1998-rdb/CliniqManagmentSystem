
import odoo
from odoo import api, SUPERUSER_ID

def find_broken_action():
    registry = odoo.registry('HMS_Test')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        actions = env['ir.actions.act_window'].search([('res_model', '=', 'res.partner')])
        print("Partner Actions Analysis:")
        for action in actions:
            if action.domain and 'user' in action.domain:
                print(f"ID: {action.id}, XML_ID: {action.get_external_id().get(action.id)}, Name: {action.name}")
                print(f"  Domain: {action.domain}")

if __name__ == "__main__":
    find_broken_action()
