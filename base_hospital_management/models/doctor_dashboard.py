from odoo import models, fields, api
from datetime import date, datetime
import logging

_logger = logging.getLogger(__name__)

class DoctorDashboard(models.Model):
    _name = 'doctor.dashboard'
    _description = 'Doctor Dashboard'
    _auto = False
    
    @api.model
    def fetch_dashboard_data(self):
        """Fetch dashboard statistics for current doctor"""
        today = date.today()
        doctor = self.env.user.partner_id
        
        # Search for today's consultations
        outpatients_today = self.env['hospital.outpatient'].search([
            ('consultation_date', '=', today),
            ('doctor_id', '=', doctor.id)
        ])
        
        # Split new vs follow-up patients
        new_patients = outpatients_today.filtered(lambda o: o.is_new_patient)
        followup_patients = outpatients_today.filtered(lambda o: not o.is_new_patient)
        
        # Consultation status
        completed = outpatients_today.filtered(lambda o: o.state == 'completed')
        pending = outpatients_today.filtered(lambda o: o.state == 'pending')
        
        # Today's collection (adjust based on your payment model)
        # This is a placeholder - modify according to your actual payment structure
        cash_collection = 0
        upi_collection = 0
        total_collection = 0
        
        # Example if you have payments linked to consultations
        for outpatient in outpatients_today:
            # Assuming there's a payment_id or payment_amount field
            if hasattr(outpatient, 'payment_amount'):
                total_collection += outpatient.payment_amount
                # You can add logic to split cash/UPI based on payment method
        
        return {
            'new_patients': len(new_patients),
            'followup_patients': len(followup_patients),
            'total_consultations': len(outpatients_today),
            'completed_consultations': len(completed),
            'pending_consultations': len(pending),
            'cash_collection': cash_collection or 4500,  # Sample data
            'upi_collection': upi_collection or 1700,    # Sample data
            'total_collection': total_collection or 6200, # Sample data
        }