from odoo import api, models


ODOO_CHAT_TEXT = "Odoo's chat helps employees collaborate efficiently. I'm here to help you discover its features."
DREAMWAREZ_CHAT_TEXT = "Dreamwarez chat helps employees collaborate efficiently. I'm here to help you discover its features."
DREAMWAREZ_APOSTROPHE_CHAT_TEXT = "Dreamwarez's chat helps employees collaborate efficiently. I'm here to help you discover its features."


def _debrand_body(body):
    if not body:
        return body
    return (
        body
        .replace(ODOO_CHAT_TEXT, DREAMWAREZ_CHAT_TEXT)
        .replace(DREAMWAREZ_APOSTROPHE_CHAT_TEXT, DREAMWAREZ_CHAT_TEXT)
    )


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if "body" in values:
                values["body"] = _debrand_body(values["body"])
        return super().create(values_list)

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE mail_message
               SET body = replace(replace(body, %s, %s), %s, %s)
             WHERE body LIKE %s
                OR body LIKE %s
            """,
            (
                ODOO_CHAT_TEXT,
                DREAMWAREZ_CHAT_TEXT,
                DREAMWAREZ_APOSTROPHE_CHAT_TEXT,
                DREAMWAREZ_CHAT_TEXT,
                f"%{ODOO_CHAT_TEXT}%",
                f"%{DREAMWAREZ_APOSTROPHE_CHAT_TEXT}%",
            ),
        )
