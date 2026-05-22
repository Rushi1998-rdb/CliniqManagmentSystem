
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class WebsiteCustomerPortal(CustomerPortal):
    """Class for inheriting _prepare_home_portal_values function """

    def _prepare_home_portal_values(self, counters):
        """Function for updating the counts of vaccinations, lab tests and op
        of portal user"""
        values = super()._prepare_home_portal_values(counters)
        if 'vaccination_count' in counters:
            values['vaccination_count'] = request.env[
                'hospital.vaccination'].sudo(). \
                search_count([('patient_id.user_ids', '=', request.uid)])
        if 'lab_test_count' in counters:
            values['lab_test_count'] = request.env['patient.lab.test'].sudo(). \
                search_count([('patient_id.user_ids', '=', request.uid)])
        if 'op_count' in counters:
            values['op_count'] = request.env[
                'hospital.outpatient'].sudo().search_count(
                [('patient_id.user_ids', '=', request.uid)])
        return values
