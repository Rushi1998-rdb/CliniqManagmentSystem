
from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    """
    Adding inpatient field to invoicing model.
    """
    _inherit = "account.payment.register"

    @api.model
    def create(self, vals_list):
        """Create records to inpatient payment"""
        self.env['inpatient.payment'].sudo().create({
            'name': vals_list['communication'],
            'subtotal': vals_list['amount'],
            'inpatient_id': self.env['hospital.inpatient'].sudo().search([(
                'patient_id', '=', vals_list['partner_id'])],
                order='create_date desc', limit=1).id,
            'date': vals_list['payment_date']
        })
        return super().create(vals_list)
