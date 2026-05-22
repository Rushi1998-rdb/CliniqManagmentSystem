
from odoo import fields, models


class DoctorSpecialization(models.Model):
    """Class holding doctor's specializations"""
    _name = 'doctor.specialization'
    _description = 'Doctor Specialization'
    _rec_name = 'specialization'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    specialization = fields.Char(string="Specialization",
                                 help='Specify the name of specialization')
