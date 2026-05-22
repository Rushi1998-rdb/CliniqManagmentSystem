
from odoo import fields, models


class LabTest(models.Model):
    """Class holding lab test details"""
    _name = 'lab.test'
    _description = 'Laboratory Test'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string='Test', help='Name of the test')
    patient_lead = fields.Float(string='Result Within',
                                help='Time taken to get the result')
    price = fields.Monetary(string='Price', help="The cost for the test")
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self:
                                  self.env.user.company_id.currency_id.id,
                                  required=True, help='Currency in which '
                                                      'payments will be done')
    tax_ids = fields.Many2many('account.tax', string='Tax',
                               help='Tax for the test')
    medicine_ids = fields.One2many('lab.medicine.line',
                                   'test_id',
                                   string='Medicines',
                                   help='Medicines used for the test')
    test_type = fields.Selection(
        [('range', 'Range'), ('objective', 'Objective')],
        string='Type', required=True, help='Type of test')
