
from odoo import api, models


class IrAttachment(models.Model):
    """Inherited for making the attachments public"""
    _inherit = 'ir.attachment'

    @api.model
    def create(self, vals):
        """Inherited to make the attachments public"""
        vals['public'] = True
        return super().create(vals)
