from odoo import api, fields, models


class CrmTag(models.Model):
    _inherit = 'crm.tag'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )


class ProductCategory(models.Model):
    _inherit = 'product.category'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        return res


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        return res


class AccountIncoterms(models.Model):
    _inherit = 'account.incoterms'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        return res


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        return res
