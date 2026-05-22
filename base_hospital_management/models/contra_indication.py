
from odoo import fields, models


class ContraIndication(models.Model):
    """Class holding the contra indications"""
    _name = 'contra.indication'
    _description = 'Contra Indication'
    _rec_name = 'blood_donation_question'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    blood_donation_question = fields.Text(string='Contra Indications',
                                          help='Contra indications of the '
                                               'blood donor')
