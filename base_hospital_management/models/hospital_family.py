
from odoo import fields, models


class HospitalFamily(models.Model):
    """Class holding hospital family details"""
    _name = 'hospital.family'
    _description = 'Hospital Family'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string="Name", help='Name of family member')
    relation = fields.Char(string="Relation", help='Relation with the patient')
    age = fields.Integer(string="Age", help='Age of family member')
    deceased = fields.Selection([('yes', 'Yes'), ('no', 'NO')],
                                string="Diseased", help='Specify whether the '
                                                        'family member is '
                                                        'alive or not')
    family_id = fields.Many2one('res.partner',
                                string="Family ID", help='Choose the family '
                                                         'member')
