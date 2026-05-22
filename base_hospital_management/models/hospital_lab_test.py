from odoo import models, fields


class HospitalLabTest(models.Model):
    _name = 'hospital.lab.test'
    _description = 'Hospital Lab Test'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string="Test Name", required=True)
    normal_range = fields.Char(string="Normal Range")
    description = fields.Text(string="Description")