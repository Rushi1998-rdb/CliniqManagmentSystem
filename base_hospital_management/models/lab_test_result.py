
from odoo import api, fields, models


class LabTestResult(models.Model):
    """Class holding lab test result"""
    _name = 'lab.test.result'
    _description = 'Lab Test Result'
    _rec_name = 'test_id'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    patient_id = fields.Many2one('res.partner', string='Patient',
                                 domain=[('patient_seq', 'not in',
                                          ['New', 'Employee', 'User'])],
                                 help='Patient for whom the test has been done')
    result = fields.Char(string='Result', help='Result of the test')
    normal = fields.Char(string='Normal', help="The normal rate of the test")
    uom_id = fields.Many2one('uom.uom', string='Unit',
                             help='Unit of the normal and result value')
    parent_id = fields.Many2one('patient.lab.test', string='Tests',
                                help='The tests for which the result'
                                     ' corresponds to')
    test_id = fields.Many2one('lab.test', string="Test Name",
                              help='Name of the test')
    attachment = fields.Binary(string='Result', help='Result document')
    currency_id = fields.Many2one('res.currency',
                                  related='test_id.currency_id',
                                  string='Currency',
                                  help='Currency in which payments to be done')
    price = fields.Monetary(string='Cost', help='Cost for the test',
                            related='test_id.price')
    tax_ids = fields.Many2many('account.tax', string='Tax',
                               help='Tax for the test')
    state = fields.Selection(selection=[('processing', 'Processing'),
                                        ('published', 'Published')],
                             string='State', help='State of the result',
                             default='processing', compute='_compute_state')

    @api.depends('attachment')
    def _compute_state(self):
        """Method for computing the state of result based on attachment"""
        for rec in self:
            if rec.attachment:
                rec.state = 'published'
            else:
                rec.state = 'processing'

    @api.model
    def print_test_results(self):
        """Method for printing rest result"""
        data = self.sudo().search([])
        context = []
        for rec in data:
            self.env.cr.execute(
                f"""SELECT id FROM ir_attachment WHERE res_id = {rec.id} 
                                            and res_model='lab.test.result' """)
            attachment_id = False
            attachment = self.env.cr.dictfetchall()
            if attachment:
                attachment_id = attachment[0]['id']
            context.append({
                'id': rec.id,
                'parent_id': rec.parent_id.test_id.name,
                'patient_id': [rec.parent_id.patient_id.id,
                               rec.parent_id.patient_id.name],
                'test_id': rec.test_id.name,
                'attachment_id': attachment_id,
                'normal': rec.normal,
                'result': rec.result,
                'unit': rec.uom_id.name if rec.uom_id else ''
            })
        return context
