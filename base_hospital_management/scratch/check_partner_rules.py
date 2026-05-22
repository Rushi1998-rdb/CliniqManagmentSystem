
import odoo
from odoo import api, SUPERUSER_ID

def check_partner_rules():
    registry = odoo.registry('HMS_Test')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        rules = env['ir.rule'].search([('model_id.model', '=', 'res.partner'), ('active', '=', True)])
        print("Active Partner Rules:")
        for rule in rules:
            print(f"Name: {rule.name}, Global: {rule.global}, Domain: {rule.domain_force}")
        
        # Test the rule logic for specific partners (e.g. from previous logs)
        partners = env['res.partner'].search([('name', 'ilike', 'LifeLinePharmacist')], limit=1)
        if partners:
            p = partners[0]
            print(f"\nTesting Partner: {p.name} (ID: {p.id})")
            print(f"  Company: {p.company_id.name} (ID: {p.company_id.id})")
            print(f"  User IDs: {p.user_ids.ids}")
            # Check which rules are rejected
            # We can't easily simulate evaluate_domain without environment context
            
if __name__ == "__main__":
    check_partner_rules()
