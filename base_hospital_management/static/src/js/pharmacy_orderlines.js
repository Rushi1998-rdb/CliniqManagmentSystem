/** @odoo-module */
import { registry} from '@web/core/registry';
import { useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
const { Component, useState } = owl
import {Dropdown} from "@web/core/dropdown/dropdown";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
    var currency=0;
export class PharmacyOrderLines extends Component {
    setup() {
        super.setup(...arguments);
        this.ref = useRef('root')
        this.orm = useService('orm')
        this.user = useService("user");
        this.actionService = useService("action");
        this.state = useState({
              product_lst :[],
              medicines :[],
              units :[],
              medicine :[],
              table_row: [{}],
              medicineSearch: "",
        });
        this.lineState = useState({
            product: this.props.line.product,
            qty: this.props.line.qty,
            uom: this.props.line.uom,
            uom_count: this.props.line.uom_count || 1,
            price: this.props.line.price,
            sub_total: this.props.line.sub_total,
        })
        this.fetch_product();
        this.fetch_uom();
        this.fetch_tax();
    }
//  Fetch product details
    async fetch_product() {
        var product_lst= [];
        var domain = [['medicine_ok', '=', true]]; // Define the search domain as a list of lists
        var result =await this.orm.call('product.template', 'search_read', [domain]);
        this.product_lst=result
        this.create_order()
    }
//   Fetch UOM of selected product
    async fetch_uom (){
        var result = await this.orm.call(
            'uom.uom',
            'search_read',
            [[], ['name', 'ratio', 'factor', 'factor_inv', 'uom_type']]
        )
        this.uom_lst = result
        this.state.units = result
    }
//  Fetch tax amount of product.
    async fetch_tax(){
        var tax_lst= [];
        var result= await this.orm.call( 'account.tax','search_read',)
        this.tax_lst=result
    }
//  Method for creating sale order
    async create_order() {
        await this.orm.call('hospital.pharmacy','company_currency',
        ).then(function (result){
           $('#symbol'+ currency).text(result || '');
           $('#symbol').text(result || '');
        })
        this.state.medicines = await this.product_lst;
        this.state.units = await this.uom_lst;
    }

    get filteredMedicines() {
        const query = (this.state.medicineSearch || "").trim().toLowerCase();
        if (!query) {
            return this.state.medicines;
        }
        return this.state.medicines.filter((med) =>
            (med.name || "").toLowerCase().includes(query)
        );
    }
// To calculate the subtotal of the medicine
    calculateSubtotal(qty, price) {
        return qty *price
    }

    getUnitQuantity(unit) {
        if (!unit) {
            return 1;
        }
        const ratio = parseFloat(unit.ratio || unit.factor_inv || 0);
        if (ratio > 0) {
            return ratio;
        }
        const factor = parseFloat(unit.factor || 0);
        if (unit.uom_type === 'bigger' && factor > 0) {
            return 1 / factor;
        }
        return 1;
    }

    updateQuantityFromUom() {
        const unit = this.state.units.find(unit => unit.id === parseInt(this.lineState.uom));
        const unitQuantity = this.getUnitQuantity(unit);
        const uomCount = parseFloat(this.lineState.uom_count) || 1;
        const qty = unitQuantity * uomCount;
        this.lineState.qty = Number.isInteger(qty) ? qty : parseFloat(qty.toFixed(5));
        this.lineState.sub_total = this.calculateSubtotal(this.lineState.qty, this.lineState.price);
        this.props.updateOrderLine(this.lineState, this.props.id);
    }
//  Method on changing the product in the sale order
    async _onChange_prod_price (med_id) {
        this.lineState.product = med_id
        const medicine = this.state.medicines.filter(med => med.id === med_id)[0]
        this.lineState.price = medicine.list_price
        this.lineState.sub_total = this.calculateSubtotal(this.lineState.qty, medicine.list_price)
        this.state.medicineSearch = ""
        this.props.updateOrderLine(this.lineState, this.props.id)
     }
//  Update quantity based on selected unit of measure
    async _onChange_uom (ev) {
        const unitId = parseInt(ev.target.value)
        this.lineState.uom = unitId
        this.updateQuantityFromUom()
    }
//  Update quantity based on selected number of units/strips
    async _onChange_uom_count () {
        if (!this.lineState.uom_count || this.lineState.uom_count < 1) {
            this.lineState.uom_count = 1
        }
        this.updateQuantityFromUom()
    }
//  Calculation of sub total based on product quantity
    async _onChange_prod_qty () {
        var self = this;
        this.lineState.sub_total = this.calculateSubtotal(this.lineState.qty, this.lineState.price)
        this.props.updateOrderLine(this.lineState, this.props.id)
    }
//  To remove the added line
    async remove_line () {
        this.props.removeLine(this.props.id)
    }
}
PharmacyOrderLines.template = "PharmacyOrderLines"
PharmacyOrderLines.components = { Dropdown, DropdownItem }
