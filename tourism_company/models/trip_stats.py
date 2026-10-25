# -*- coding: utf-8 -*-
"""طبقة الإحصائيات: كل أرقام الـ Dashboard والتقرير الشهري بتتحسب من هنا."""
from collections import Counter, defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

TOP_N = 5
UPCOMING_DAYS = 7
MONTHS_BACK = 12

MONTHS = [
    ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'), ('4', 'أبريل'),
    ('5', 'مايو'), ('6', 'يونيو'), ('7', 'يوليو'), ('8', 'أغسطس'),
    ('9', 'سبتمبر'), ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
]


class TripPeriodMixin(models.AbstractModel):
    """حقول الشهر والسنة المشتركة بين الـ Dashboard ونافذة الطباعة."""
    _name = 'trip.period.mixin'
    _description = 'اختيار الشهر والسنة'

    month = fields.Selection(
        MONTHS, string='الشهر',
        default=lambda self: str(fields.Date.context_today(self).month),
    )
    year = fields.Selection(
        selection='_selection_year', string='السنة',
        default=lambda self: str(fields.Date.context_today(self).year),
    )

    @api.model
    def _selection_year(self):
        current = fields.Date.context_today(self).year
        return [(str(y), str(y)) for y in range(current - 6, current + 2)]

    def _month_range(self):
        self.ensure_one()
        start = date(int(self.year), int(self.month), 1)
        return start, start + relativedelta(months=1, days=-1)

    def _month_label(self):
        self.ensure_one()
        return '%s %s' % (dict(MONTHS).get(self.month, ''), self.year)


class TripStats(models.AbstractModel):
    _name = 'trip.stats'
    _description = 'إحصائيات التشغيل'

    @api.model
    def _dom(self, field_name, date_from, date_to):
        domain = []
        if date_from:
            domain.append((field_name, '>=', date_from))
        if date_to:
            domain.append((field_name, '<=', date_to))
        return domain

    @api.model
    def get_data(self, date_from=False, date_to=False):
        """يرجع كل الأرقام لفترة معينة (أو كل الفترات لو التواريخ فاضية)."""
        env = self.env
        today = fields.Date.context_today(self)

        # ------------------------------------------------------------ الرحلات
        trips = env['trip.order'].search(
            self._dom('trip_date', date_from, date_to), order='trip_date, id')
        counted = trips.filtered(lambda t: t.state in ('confirmed', 'done'))

        veh = defaultdict(lambda: {'trips': 0, 'km': 0.0, 'fuel': 0.0})
        drv = defaultdict(lambda: {'trips': 0, 'km': 0.0, 'passengers': 0})
        for t in counted:
            v = veh[t.vehicle_id.id]
            v['name'] = t.vehicle_id.display_name
            v['trips'] += 1
            v['km'] += t.distance
            v['fuel'] += t.fuel_total
            d = drv[t.driver_id.id]
            d['name'] = t.driver_id.display_name
            d['trips'] += 1
            d['km'] += t.distance
            d['passengers'] += t.passengers_count

        def top(values, key):
            return sorted(values, key=key)[:TOP_N]

        top_vehicles = top(veh.values(), lambda x: (-x['trips'], -x['km']))
        top_drivers = top(drv.values(), lambda x: (-x['trips'], -x['km']))

        dest_labels = dict(env['trip.order']._fields['destination'].selection)
        dest_counter = Counter(t.destination for t in counted)
        destinations = [
            {'name': dest_labels.get(k, k), 'trips': c}
            for k, c in dest_counter.most_common(TOP_N)
        ]

        month_counter = Counter(
            t.trip_date.strftime('%Y-%m') for t in counted if t.trip_date)
        monthly = [
            {'name': k, 'trips': month_counter[k]}
            for k in sorted(month_counter)[-MONTHS_BACK:]
        ]

        # ------------------------------------------------- الصيانة الشهرية
        maints = env['vehicle.maintenance'].search(
            self._dom('maintenance_date', date_from, date_to)
            + [('state', '!=', 'cancelled')])
        mveh = defaultdict(lambda: {'count': 0, 'cost': 0.0})
        mtypes = defaultdict(float)
        type_labels = dict(
            env['vehicle.maintenance']._fields['maintenance_type'].selection)
        for m in maints:
            r = mveh[m.vehicle_id.id]
            r['name'] = m.vehicle_id.display_name
            r['count'] += 1
            r['cost'] += m.cost
            mtypes[type_labels.get(m.maintenance_type, '-')] += m.cost
        top_maint = top(mveh.values(), lambda x: (-x['cost'], -x['count']))
        maint_types = [
            {'name': k, 'cost': v}
            for k, v in sorted(mtypes.items(), key=lambda kv: -kv[1])
        ]

        # ----------------------------------------- الصيانة قبل الاستلام
        handovers = env['vehicle.handover'].search(
            self._dom('date', date_from, date_to))
        hveh = defaultdict(lambda: {'count': 0, 'failed': 0})
        for h in handovers:
            r = hveh[h.vehicle_id.id]
            r['name'] = h.vehicle_id.display_name
            r['count'] += 1
            r['failed'] += len(h.line_ids.filtered('is_no'))
        top_handover = top(
            hveh.values(), lambda x: (-x['failed'], -x['count']))

        # ------------------------------------------- حالة العربيات والسواقين
        vehicles = env['vehicle.vehicle'].search([])
        drivers = env['driver.profile'].search([])
        fleet = Counter(vehicles.mapped('state'))
        crew = Counter(drivers.mapped('state'))

        # ---------------------------------------------------- التنبيهات
        alerts = []

        def add_alert(kind, who, expiry, status):
            alerts.append({
                'kind': kind, 'who': who, 'date': expiry, 'status': status,
                'days': (expiry - today).days if expiry else 0,
            })

        for v in vehicles:
            if v.license_alert_state != 'ok':
                add_alert('رخصة عربية', v.plate_number,
                          v.license_expiry_date, v.license_alert_state)
            if v.insurance_alert_state != 'ok':
                add_alert('تأمين عربية', v.plate_number,
                          v.insurance_expiry_date, v.insurance_alert_state)
        for d in drivers:
            if d.license_alert_state != 'ok':
                add_alert('رخصة سائق', d.name,
                          d.license_expiry_date, d.license_alert_state)
        alerts.sort(key=lambda a: a['days'])

        upcoming = []
        limit = today + relativedelta(days=UPCOMING_DAYS)
        for v in vehicles:
            last = v.maintenance_ids.filtered(
                lambda m: m.state != 'cancelled'
            ).sorted(lambda m: (m.maintenance_date, m.id), reverse=True)[:1]
            if last and last.next_maintenance_date \
                    and last.next_maintenance_date <= limit:
                upcoming.append({
                    'who': v.plate_number,
                    'date': last.next_maintenance_date,
                    'days': (last.next_maintenance_date - today).days,
                })
        upcoming.sort(key=lambda a: a['days'])

        # ------------------------------------------------------ الإجماليات
        fuel_cost = sum(counted.mapped('fuel_total'))
        maint_cost = sum(maints.mapped('cost'))
        km = sum(counted.mapped('distance'))
        totals = {
            'trips_all': len(trips),
            'draft': len(trips.filtered(lambda t: t.state == 'draft')),
            'confirmed': len(trips.filtered(lambda t: t.state == 'confirmed')),
            'done': len(trips.filtered(lambda t: t.state == 'done')),
            'cancelled': len(trips.filtered(lambda t: t.state == 'cancelled')),
            'km': km,
            'fuel_liters': sum(counted.mapped('fuel_consumed')),
            'fuel_cost': fuel_cost,
            'passengers': sum(counted.mapped('passengers_count')),
            'maint_count': len(maints),
            'maint_cost': maint_cost,
            'handover_count': len(handovers),
            'total_cost': fuel_cost + maint_cost,
            'cost_per_km': (fuel_cost + maint_cost) / km if km else 0.0,
        }

        # ------------------------------------- تفاصيل الكروت (قايمة السجلات)
        state_labels = dict(env['trip.order']._fields['state'].selection)
        trip_rows = [{
            'name': t.display_name,
            'date': t.trip_date,
            'vehicle': t.vehicle_id.display_name,
            'driver': t.driver_id.display_name,
            'destination': dest_labels.get(t.destination, t.destination),
            'state': state_labels.get(t.state, t.state),
            'counted': t.state in ('confirmed', 'done'),
            'km': t.distance,
            'passengers': t.passengers_count,
            'fuel_liters': t.fuel_consumed,
            'fuel_cost': t.fuel_total,
        } for t in trips]
        maint_rows = [{
            'name': m.display_name,
            'date': m.maintenance_date,
            'vehicle': m.vehicle_id.display_name,
            'type': type_labels.get(m.maintenance_type, '-'),
            'cost': m.cost,
        } for m in maints.sorted(
            lambda m: (m.maintenance_date or date.min, m.id), reverse=True)]
        handover_rows = [{
            'date': h.date,
            'vehicle': h.vehicle_id.display_name,
            'failed': len(h.line_ids.filtered('is_no')),
            'checks': len(h.line_ids),
        } for h in handovers.sorted(
            lambda h: (h.date or date.min, h.id), reverse=True)]

        return {
            'totals': totals,
            'trips': trips,
            'trip_rows': trip_rows,
            'maint_rows': maint_rows,
            'handover_rows': handover_rows,
            'top_vehicles': top_vehicles,
            'top_drivers': top_drivers,
            'destinations': destinations,
            'monthly': monthly,
            'top_maint': top_maint,
            'maint_types': maint_types,
            'top_handover': top_handover,
            'fleet': {
                'total': len(vehicles),
                'available': fleet.get('available', 0),
                'on_trip': fleet.get('on_trip', 0),
                'out_of_service': fleet.get('out_of_service', 0),
            },
            'crew': {
                'total': len(drivers),
                'available': crew.get('available', 0),
                'on_trip': crew.get('on_trip', 0),
                'off': crew.get('off', 0),
                'suspended': crew.get('suspended', 0),
            },
            'alerts': alerts,
            'upcoming': upcoming,
        }