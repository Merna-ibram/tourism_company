# -*- coding: utf-8 -*-
from odoo import api, models


class TripMonthlyReportWizard(models.TransientModel):
    """نافذة اختيار الشهر قبل طباعة التقرير الشهري."""
    _name = 'trip.monthly.report.wizard'
    _inherit = ['trip.period.mixin']
    _description = 'طباعة تقرير شهري'

    def action_print(self):
        self.ensure_one()
        return self.env.ref(
            'tourism_company.action_report_trip_monthly'
        ).report_action(self)


class ReportTripMonthly(models.AbstractModel):
    _name = 'report.tourism_company.report_trip_monthly'
    _description = 'التقرير الشهري'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['trip.monthly.report.wizard'].browse(docids)
        wizard = docs[:1]
        date_from, date_to = wizard._month_range()
        return {
            'doc_ids': docids,
            'doc_model': 'trip.monthly.report.wizard',
            'docs': docs,
            'data': self.env['trip.stats'].get_data(date_from, date_to),
            'period_label': wizard._month_label(),
            'company_name': self.env.company.name,
            'currency': self.env.company.currency_id.symbol or '',
            'fmt': lambda value, decimals=0: '{:,.{d}f}'.format(
                value or 0, d=decimals),
            'dest_labels': dict(
                self.env['trip.order']._fields['destination'].selection),
            'state_labels': {
                'draft': 'مسودة', 'confirmed': 'مؤكدة',
                'done': 'منتهية', 'cancelled': 'ملغاة',
            },
        }