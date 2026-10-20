# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VehicleHandover(models.Model):
    _inherit = 'vehicle.handover'

    trip_id = fields.Many2one(
        'trip.order',
        string='أمر التشغيل',
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # ربط الرحلة بالصيانة (لو الصيانة اتفتحت من الرحلة)
        for rec in records:
            if rec.trip_id and not rec.trip_id.handover_id:
                rec.trip_id.handover_id = rec
        return records

    @api.constrains('trip_id', 'vehicle_id', 'driver_id')
    def _check_trip_match(self):
        for rec in self:
            t = rec.trip_id
            if t and (t.vehicle_id != rec.vehicle_id or t.driver_id != rec.driver_id):
                raise ValidationError(_('العربية والسائق لازم يكونوا نفس البيانات في أمر التشغيل.'))

    def action_save_open_trip(self):
        """يحفظ الصيانة (الزر بيحفظ تلقائي) ويفتح أمر التشغيل."""
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('أمر التشغيل'),
            'res_model': 'trip.order',
            'view_mode': 'form',
            'target': 'current',
        }
        if self.trip_id:
            action['res_id'] = self.trip_id.id
        else:
            action['context'] = {
                'default_vehicle_id': self.vehicle_id.id,
                'default_driver_id': self.driver_id.id,
                'default_odometer_start': self.odometer,
                'default_handover_id': self.id,
            }
        return action