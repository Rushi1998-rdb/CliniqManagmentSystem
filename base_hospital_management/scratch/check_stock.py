import sys
sys.path.append(r'c:\Program Files\Odoo 17.0.20251119\server')
import odoo
from odoo import api, SUPERUSER_ID
import sys

# Initialize Odoo environment
try:
    odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 17.0.20251119\server\odoo.conf', '-d', 'Server_db_18_May'])
    registry = odoo.registry('Server_db_18_May')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        product = env['product.product'].search([('name', 'ilike', 'serverCompanyMedicine')], limit=1)
        if product:
            print(f"Product: {product.name} (ID: {product.id})")
            print(f"On Hand (qty_available): {product.qty_available}")
            print(f"Free Qty: {product.free_qty}")
            print(f"Reserved (outgoing_qty): {product.outgoing_qty}")
            print(f"Incoming: {product.incoming_qty}")
            
            print("\n--- Stock Quants (Internal Locations) ---")
            quants = env['stock.quant'].search([('product_id', '=', product.id), ('location_id.usage', '=', 'internal')])
            for q in quants:
                print(f"Location: {q.location_id.complete_name}, Qty: {q.quantity}, Reserved: {q.reserved_quantity}, Company: {q.company_id.name}")
                
            print("\n--- Pending Stock Moves ---")
            moves = env['stock.move'].search([('product_id', '=', product.id), ('state', 'not in', ('done', 'cancel'))])
            for m in moves:
                print(f"Move: {m.reference}, State: {m.state}, From: {m.location_id.name} To: {m.location_dest_id.name}, Qty: {m.product_uom_qty}, Reserved: {m.quantity}")
                
        else:
            print("Product not found")
except Exception as e:
    print(f"Error: {e}")
