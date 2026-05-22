
import odoo
from odoo import api, SUPERUSER_ID

def check_rules():
    registry = odoo.registry('HMS_Test')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        models = ['res.users', 'res.partner', 'hr.employee']
        print("Record Rule Analysis:")
        for model_name in models:
            model = env['ir.model'].search([('model', '=', model_name)], limit=1)
            rules = env['ir.rule'].search([('model_id', '=', model.id), ('active', '=', True)])
            print(f"\nModel: {model_name}")
            for r in rules:
                print(f"  Rule: {r.name} (ID: {r.id}, Global: {r.global})")
                print(f"    Domain: {r.domain_force}")
                print(f"    Groups: {[g.name for g in r.groups_id]}")

if __name__ == "__main__":
    check_rules()
