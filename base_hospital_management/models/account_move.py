from odoo import api, fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    outpatient_id = fields.Many2one('hospital.outpatient', string='Outpatient Record', readonly=True)

    def _compute_payment_state(self):
        super(AccountMove, self)._compute_payment_state()
        for move in self:
            if move.outpatient_id and move.payment_state in ('paid', 'in_payment'):
                if move.outpatient_id.state != 'done':
                    move.outpatient_id.state = 'done'
