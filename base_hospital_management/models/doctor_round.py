
from odoo import fields, models


class DoctorRound(models.Model):
    """Class holding doctor round details"""
    _name = 'doctor.round'
    _description = "Doctor Rounds"

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    admission_id = fields.Many2one('hospital.inpatient',
                                   string='Patient',
                                   help='Choose the patient')
    doctor_id = fields.Many2one('hr.employee',
                                domain=[('job_id.name', '=', 'Doctor')],
                                string='Doctor', help='Choose your doctor')
    date = fields.Datetime(string='Visit Time', help='Choose the visit time '
                                                     'of doctor')
    status = fields.Char(string='Status', help='Status of doctor rounds')
    notes = fields.Text(string='Note', help='Notes regarding the rounds')
