from odoo import models, fields

class CreatePatientWizard(models.TransientModel):
    _name = 'create.patient.wizard'
    _description = 'Create Patient Wizard'

    name = fields.Char(string="Patient Name", required=True)
    phone = fields.Char(string="Phone", required=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ])
    date_of_birth = fields.Date(string="Date of Birth")

    def action_create_patient(self):
        partner = self.env['res.partner'].create({
            'name': self.name,
            'phone': self.phone,
            'gender': self.gender,
            'date_of_birth': self.date_of_birth,
        })

        return {
            'type': 'ir.actions.act_window_close'
        }