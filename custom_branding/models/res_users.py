from markupsafe import Markup

from odoo import _, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _init_odoobot(self):
        self.ensure_one()
        bot_partner_id = self.env["ir.model.data"]._xmlid_to_res_id("base.partner_root")
        channel = self.env["discuss.channel"].channel_get([bot_partner_id, self.partner_id.id])
        message = Markup("%s<br/>%s<br/><b>%s</b> <span class=\"o_odoobot_command\">:)</span>") % (
            _("Hello,"),
            _("Dreamwarez chat helps employees collaborate efficiently. I'm here to help you discover its features."),
            _("Try to send me an emoji"),
        )
        channel.sudo().message_post(
            body=message,
            author_id=bot_partner_id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self.sudo().odoobot_state = "onboarding_emoji"
        return channel
