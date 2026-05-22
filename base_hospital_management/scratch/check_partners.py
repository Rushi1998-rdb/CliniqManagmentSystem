
import odoo
from odoo import api, SUPERUSER_ID

def check_partners():
    # Load the registry
    registry = odoo.registry('HMS_Test')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        partner_ids = [3, 7, 77, 166, 167]
        partners = env['res.partner'].browse(partner_ids)
        print("Partner Analysis:")
        for p in partners:
            print(f"ID: {p.id}, Name: {p.name}, Company: {p.company_id.name} ({p.company_id.id}), UserIDs: {p.user_ids.ids}")

if __name__ == "__main__":
    check_partners()
