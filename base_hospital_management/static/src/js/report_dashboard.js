/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class ReportDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            cards: [],
            breakdown: [],
            breakdown_total: "",
            revenue_chart: [],
            revenue_total: "",
            quick_stats: {},
            transactions: [],
            breakdown_period: "today",
            revenue_period: "month",
            transaction_start: "",
            transaction_end: "",
            company_name: "",
        });

        onWillStart(async () => {
            const today = this.getTodayString();
            this.state.transaction_start = today;
            this.state.transaction_end = today;
            await this.loadDashboard();
        });
    }

    getTodayString() {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, "0");
        const day = String(today.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    async loadDashboard() {
        const data = await this.orm.call("hospital.outpatient", "fetch_report_dashboard_data", [], {
            breakdown_period: this.state.breakdown_period,
            revenue_period: this.state.revenue_period,
            transaction_start: this.state.transaction_start,
            transaction_end: this.state.transaction_end,
        });

        this.state.cards = data.cards || [];
        this.state.breakdown = data.breakdown || [];
        this.state.breakdown_total = data.breakdown_total || "";
        this.state.revenue_chart = data.revenue_chart || [];
        this.state.revenue_total = data.revenue_total || "";
        this.state.quick_stats = data.quick_stats || {};
        this.state.transactions = data.transactions || [];
        this.state.company_name = data.company_name || "";
        this.state.transaction_start = data.transaction_start || this.state.transaction_start;
        this.state.transaction_end = data.transaction_end || this.state.transaction_end;
    }

    async onBreakdownPeriodChange(ev) {
        this.state.breakdown_period = ev.target.value;
        await this.loadDashboard();
    }

    async onRevenuePeriodChange(ev) {
        this.state.revenue_period = ev.target.value;
        await this.loadDashboard();
    }

    onTransactionDateChange(field, ev) {
        this.state[field] = ev.target.value;
    }

    async generateTransactions() {
        await this.loadDashboard();
    }

    async openCardRecords(periodKey) {
        const action = await this.orm.call(
            "hospital.outpatient",
            "action_open_report_period",
            [periodKey]
        );
        if (action) {
            this.actionService.doAction(action);
        }
    }

    printDashboard() {
        window.print();
    }

    exportTransactions() {
        const rows = [
            ["Date", "OP Number", "Patient Number", "Patient Name", "Type", "Doctor", "Service", "Amount", "Time"],
            ...this.state.transactions.map((tx) => ([
                tx.date || "",
                tx.op_number || "",
                tx.patient_number || "",
                tx.patient_name || "",
                tx.type || "",
                tx.doctor || "",
                tx.service || "",
                tx.amount || 0,
                tx.time || "",
            ])),
        ];
        const csv = rows
            .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","))
            .join("\n");
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "report_dashboard_transactions.csv";
        link.click();
        URL.revokeObjectURL(url);
    }

    chartStyle() {
        const colors = {
            consultation: "#14b8a6",
            injection: "#3b82f6",
            dressing: "#a855f7",
            lab_test: "#f59e0b",
            others: "#94a3b8",
        };
        let start = 0;
        const segments = [];
        for (const item of this.state.revenue_chart) {
            const end = start + item.percentage;
            const color = colors[item.service_key] || "#cbd5e1";
            segments.push(`${color} ${start}% ${end}%`);
            start = end;
        }
        if (start < 100) {
            segments.push(`#e2e8f0 ${start}% 100%`);
        }
        return `background: conic-gradient(${segments.join(", ")});`;
    }

    serviceColor(serviceKey) {
        const colors = {
            consultation: "teal",
            injection: "blue",
            dressing: "violet",
            lab_test: "amber",
            others: "slate",
        };
        return `report-dashboard__dot--${colors[serviceKey] || "slate"}`;
    }
}

ReportDashboard.template = "ReportDashboard";
registry.category("actions").add("report_dashboard_tags", ReportDashboard);
