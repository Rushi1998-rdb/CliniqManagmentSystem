
from odoo import fields, models


class BloodDonation(models.Model):
    """Class holding blood donation details"""
    _name = 'blood.donation'
    _description = 'Blood Donation'
    _rec_name = 'questions'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    questions = fields.Text(string='Contra Indications',
                            help='Contraindications of the blood donor')
    is_true = fields.Boolean(string='Is True',
                             help='True for contraindications')
    blood_bank_id = fields.Many2one('blood.bank',
                                    string='Blood Bank',
                                    help='Blood bank corresponding to the '
                                         'donor')
