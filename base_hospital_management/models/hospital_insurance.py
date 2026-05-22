
from odoo import fields, models


class HospitalInsurance(models.Model):
    """Class holding insurance details"""
    _name = 'hospital.insurance'
    _description = 'Hospital Insurance'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string='Provider', help='Name of the insurance provider')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  help='Currency in which insurance will be '
                                       'calculated',
                                  default=lambda self: self.env.user.company_id
                                  .currency_id.id,
                                  required=True)
    total_coverage = fields.Monetary(string='Total Coverage',
                                     help='Total coverage of the insurance')
