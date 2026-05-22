
import odoo
from odoo import api, SUPERUSER_ID

def debug_partners():
    registry = odoo.registry('HMS_Test')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        partner_names = ['Admin1', 'Administrator', 'Life', 'Life1', 'LifeHospitalPharmacist']
        partners = env['res.partner'].search([('name', 'in', partner_names)])
        print(f"{'Name':<30} | {'Company':<20} | {'Linked User(s)':<20} | {'User Company':<20}")
        print("-" * 100)
        for p in partners:
            user_info = ", ".join(p.user_ids.mapped('name'))
            user_company = ", ".join(p.user_ids.mapped('company_id.name'))
            print(f"{p.name:<30} | {p.company_id.name or 'False':<20} | {user_info:<20} | {user_company:<20}")

if __name__ == "__main__":
    debug_partners()
