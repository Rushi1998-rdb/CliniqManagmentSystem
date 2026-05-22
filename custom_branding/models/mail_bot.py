from odoo import models


class MailBot(models.AbstractModel):
    _inherit = "mail.bot"

    def _get_answer(self, record, body, values, command=False):
        answer = super()._get_answer(record, body, values, command=command)
        if not answer:
            return answer
        return (
            answer
            .replace("Odoo's chat", "Dreamwarez chat")
            .replace("Dreamwarez's chat", "Dreamwarez chat")
            .replace("discovering Odoo!", "discovering Dreamwarez!")
        )
