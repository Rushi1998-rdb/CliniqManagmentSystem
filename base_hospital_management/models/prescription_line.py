from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import re
import math

_logger = logging.getLogger(__name__)

class PrescriptionLine(models.Model):
    """Class holding prescription line details"""
    _name = 'prescription.line'
    _description = 'Prescription Lines'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')
    _rec_name = 'medicine_id'

    # prescription_id = fields.Many2one(
    #     'hospital.prescription',
    #     string='Prescription',
    #     help='Name of the prescription'
    # )
    
    medicine_id = fields.Many2one(
        'product.template', 
        domain="['|', ('medicine_ok', '=', True), ('vaccine_ok', '=', True)]",
        string='Medicine', 
        required=True,
        help='Medicines or vaccines'
    )

    medicine_type = fields.Selection(
        related='medicine_id.medicine_type',
        string='Type',
        readonly=True
    )

    dosage_uom = fields.Selection(
        related='medicine_id.dosage_uom',
        string='Dosage Unit',
        readonly=True
    )

    volume_per_bottle = fields.Float(
        related='medicine_id.volume_per_bottle',
        string='Vol/Bottle',
        readonly=True
    )
    
    quantity = fields.Integer(
        string='Quantity (Bottles/Units)', 
        compute='_compute_quantity',
        store=True,
        help="The number of bottles or units to be dispensed"
    )

    total_dosage_display = fields.Char(
        string='Total Requirement',
        compute='_compute_quantity',
        store=True,
        help="Total volume or quantity required (e.g. 600 ml)"
    )

    # Use Char to allow "5ml", "10ml", etc.
    no_intakes = fields.Char(
        string='Intakes per time', 
        required=True,
        default='1',
        help="Amount to take (e.g. 1, 5ml, 2 tablets)"
    )
    
    days = fields.Integer(
        string='Days', 
        required=True,
        default=1,
        help="Number of days the medicine should be taken"
    )
    
    note = fields.Selection(
        [('before', 'Before Food'), ('after', 'After Food')],
        string='Before/After Food (Legacy)',
        help='Legacy field - use selected times for new prescriptions',
        default='before'
    )
    
    selected_times = fields.Many2many(
        'prescription.time',
        string='Intake Times',
        required=True,  # Make this required to ensure at least one time is selected
        help='Selected times for medicine intake'
    )
    
    custom_schedule = fields.Char(
        string='Custom Schedule',
        help='Enter custom schedule instructions'
    )
    
    inpatient_id = fields.Many2one(
        'hospital.inpatient',
        string='Inpatient',
        help='The inpatient corresponds to the prescription line'
    )
    
    outpatient_id = fields.Many2one(
        'hospital.outpatient',
        string='Outpatient',
        help='The outpatient corresponds to the prescription line'
    )
    
    res_partner_id = fields.Many2one(
        'res.partner',
        string='Patient',
        help='The outpatient corresponds to the prescription line',
        related='outpatient_id.patient_id'
    )



    @api.depends('no_intakes', 'days', 'selected_times', 'medicine_id.volume_per_bottle', 'medicine_id.dosage_uom')
    def _compute_quantity(self):
        for record in self:
            try:
                record.quantity = 0
                record.total_dosage_display = ""
                
                if not record.selected_times or record.days < 1 or not record.no_intakes:
                    continue
                
                # Parse numeric part from no_intakes (e.g., "5ml" -> 5.0)
                numeric_match = re.search(r"[-+]?\d*\.?\d+", record.no_intakes)
                amount = float(numeric_match.group()) if numeric_match else 0.0

                if amount <= 0:
                    continue

                # Count the number of selected times
                count = len(record.selected_times)
                
                total_dosage = amount * count * record.days
                
                # If it's a liquid (ml, mg, etc.) and we have a volume per bottle
                if record.dosage_uom != 'unit' and record.volume_per_bottle > 0:
                    # Quantity = Number of bottles needed (round up)
                    record.quantity = int(math.ceil(total_dosage / record.volume_per_bottle))
                    record.total_dosage_display = f"{total_dosage:g} {record.dosage_uom}"
                else:
                    # Quantity = Total units (tablets/capsules)
                    record.quantity = int(total_dosage)
                    record.total_dosage_display = f"{int(total_dosage)} Units"
                
            except Exception as e:
                record.quantity = 0
                record.total_dosage_display = "Error"
                _logger.error(f"Error calculating quantity: {str(e)}")

    @api.constrains('days')
    def _check_positive_values(self):
        for record in self:
            if record.days < 1:
                raise UserError(_("Days must be at least 1"))

class PrescriptionTime(models.Model):
    _name = 'prescription.time'
    _description = 'Prescription Time Options'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=False,
                                 help='Indicates the company')
    
    name = fields.Char(string='Display Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')

    @api.model
    def _standard_time_options(self):
        return [
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
            ('evening', 'Evening'),
        ]

    def init(self):
        """Clean up deprecated options and link standard ones to XML IDs."""
        super().init()
        cr = self.env.cr
        
        # 1. Clean up truly deprecated intake options
        unwanted_codes = [
            'morning_before', 'morning_after', 
            'afternoon_before', 'afternoon_after', 
            'evening_before', 'evening_after', 
            'custom'
        ]
        cr.execute("SELECT id FROM prescription_time WHERE code IN %s", [tuple(unwanted_codes)])
        ids_to_delete = [r[0] for r in cr.fetchall()]
        if ids_to_delete:
            _logger.info(f"Cleaning up deprecated intake time IDs: {ids_to_delete}")
            cr.execute("DELETE FROM prescription_line_prescription_time_rel WHERE prescription_time_id IN %s", [tuple(ids_to_delete)])
            cr.execute("DELETE FROM prescription_time WHERE id IN %s", [tuple(ids_to_delete)])
        
        # Migrating 'night' to 'evening' if it exists to maintain user data
        cr.execute("UPDATE prescription_time SET code = 'evening', name = 'Evening' WHERE code = 'night'")
        
        # 2. Link existing standard records to XML IDs to prevent UniqueViolation during XML load
        for code in ['morning', 'afternoon', 'evening']:
            cr.execute("SELECT id FROM prescription_time WHERE code = %s", [code])
            res = cr.fetchone()
            if res:
                rec_id = res[0]
                # Map standard codes to their corresponding XML IDs in base_hospital_management
                # Note: 'evening' maps to 'prescription_time_night' because we reused that record ID
                xml_id_map = {
                    'morning': 'prescription_time_morning',
                    'afternoon': 'prescription_time_afternoon',
                    'evening': 'prescription_time_night'
                }
                xml_id = xml_id_map[code]
                
                # Check if it's already linked
                cr.execute("SELECT id FROM ir_model_data WHERE model = 'prescription.time' AND res_id = %s", [rec_id])
                if not cr.fetchone():
                    # Link it
                    cr.execute("""
                        INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
                        VALUES (%s, 'base_hospital_management', 'prescription.time', %s, true)
                    """, [xml_id, rec_id])
        cr.commit()

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'A time option with this code already exists.')
    ]
