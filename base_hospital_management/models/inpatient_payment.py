
from odoo import fields, models


class InpatientPayment(models.Model):
    """Class holding Payment details of Inpatient"""
    _name = 'inpatient.payment'
    _description = "Inpatient Payments"

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string='Name', help='Name of payment')
    subtotal = fields.Float(string='Subtotal', help='Total payment')
    inpatient_id = fields.Many2one('hospital.inpatient',
                                   string='Inpatient',
                                   help='Inpatient related to the payment')
    date = fields.Datetime(string='Date', help="Date of payment")
    tax_ids = fields.Many2many('account.tax', string='Tax',
                               help='Tax for the test')
