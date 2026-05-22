from odoo import api, fields, models
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False, date=None):
        """
        Override to automatically heal missing accounting properties on Patients and Products
        before generating the invoice. This prevents the 'Missing required account' SQL constraint error.
        """
        for order in self:
            company = order.company_id
            
            # 1. Auto-heal Patient Receivable Account
            patient = order.partner_id.with_company(company)
            if not patient.property_account_receivable_id:
                receivable_account = self.env['account.account'].sudo().search([
                    ('account_type', '=', 'asset_receivable'),
                    ('company_id', '=', company.id)
                ], limit=1)
                
                if receivable_account:
                    patient.sudo().property_account_receivable_id = receivable_account.id
                else:
                    raise ValidationError(f"No Receivable Account exists for company {company.name}. Please configure your Chart of Accounts.")

            # 2. Auto-heal Product Category Income Account
            for line in order.order_line:
                product = line.product_id
                if product:
                    # Check if product or its category has an income account
                    has_income_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
                    if not has_income_account:
                        income_account = self.env['account.account'].sudo().search([
                            ('account_type', 'in', ['income', 'income_other']),
                            ('company_id', '=', company.id)
                        ], limit=1)
                        
                        if income_account:
                            # Attach it to the category so all future products in this category are fixed
                            product.categ_id.sudo().property_account_income_categ_id = income_account.id
                        else:
                            raise ValidationError(f"No Income Account exists for company {company.name}. Please configure your Chart of Accounts.")

        return super(SaleOrder, self)._create_invoices(grouped=grouped, final=final, date=date)
