
from odoo import api, models, fields


class ResUsers(models.Model):
    """Inherited to prevent creating patients while creating users"""
    _inherit = 'res.users'

    notification_type = fields.Selection(
        selection_add=[('inbox', 'Handle in Dreamwarez')],
        ondelete={'inbox': 'cascade'}
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override to add patient_seq to the partners created from users"""
        users = super().create(vals_list)
        for user in users:
            user.partner_id.write({
                'patient_seq': 'User',
                'company_id': False,
            })
        return users

    @api.model
    def get_current_company_id(self):
        """Return the active company id for the current session."""
        return self.env.company.id
