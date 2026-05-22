from odoo import models, fields, api


class HospitalLabResult(models.Model):
    _name = 'hospital.lab.result'
    _description = 'Hospital Lab Result'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )

    patient_id = fields.Many2one(
        'res.partner',
        string="Patient",
        required=True
    )

    outpatient_id = fields.Many2one(
        'hospital.outpatient',
        string="Outpatient"
    )

    test_id = fields.Many2one(
        'hospital.lab.test',
        string="Test Name",
        required=True
    )

    ordered_date = fields.Date(
        string="Ordered Date",
        default=fields.Date.today
    )

    result_value = fields.Char(string="Result Value")

    normal_range = fields.Char(string="Normal Range")

    lab_test_charge = fields.Monetary(
        string="Lab Test Charges",
        currency_field='currency_id'
    )

    status = fields.Selection(
        [
            ('ordered', 'Ordered'),
            ('received', 'Received'),
            ('reviewed', 'Reviewed')
        ],
        default='ordered',
        string="Status"
    )

    picture = fields.Binary(string="Picture Upload")

    report_file = fields.Binary(string="Upload Report")

    report_filename = fields.Char()

    doctor_remarks = fields.Text(string="Doctor Remarks")

    @api.onchange('test_id')
    def _onchange_test_id(self):
        for rec in self:
            if rec.test_id:
                rec.normal_range = rec.test_id.normal_range
