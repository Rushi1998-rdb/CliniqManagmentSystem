
from odoo import fields, models


class HospitalDegree(models.Model):
    """Class holding degree details of Doctor"""
    _name = 'hospital.degree'
    _description = 'Degree'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string="Degree", help='Degree of the staff')
