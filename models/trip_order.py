# -*- coding: utf-8 -*-
from datetime import datetime, time

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

LOCATIONS = [
    ('cairo', 'القاهرة'),
    ('alexandria', 'الإسكندرية'),
    ('north_coast', 'الساحل'),
    ('dahab', 'دهب'),
    ('sharm', 'شرم'),
    ('egyptian_museum', 'المتحف المصري'),
]

START_POINTS = [
    ('cairo', 'القاهرة'),
    ('alexandria', 'الإسكندرية'),
]

# حالات العربية والسائق اللي مينفعش يتحجزوا فيها
VEHICLE_BLOCKED_STATES = ('out_of_service',)
DRIVER_BLOCKED_STATES = ('off', 'suspended')


class TripOrder(models.Model):
    _name = 'trip.order'
    _description = 'أمر التشغيل'
    _inherit = ['mail.thread']
    _order = 'trip_date desc, id desc'

    name = fields.Char(
        string='رقم الرحلة',
        readonly=True,
        copy=False,
        default='جديد',
    )
    vehicle_id = fields.Many2one(
        'vehicle.vehicle',
        string='العربية',
        required=True,
        tracking=True,
    )
    driver_id = fields.Many2one(
        'driver.profile',
        string='اسم السائق',
        required=True,
        tracking=True,
    )
    # العربيات والسواقين المتاحين في فترة الرحلة (بتتحسب من المواعيد)
    available_vehicle_ids = fields.Many2many(
        'vehicle.vehicle',
        compute='_compute_available_resources',
    )
    available_driver_ids = fields.Many2many(
        'driver.profile',
        compute='_compute_available_resources',
    )
    trip_date = fields.Date(
        string='تاريخ الرحلة',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    departure_datetime = fields.Datetime(
        string='وقت التحرك',
        required=True,
    )
    arrival_datetime = fields.Datetime(
        string='وقت الوصول',
        required=True,
    )
    start_point = fields.Selection(
        START_POINTS,
        string='نقطة البداية',
        required=True,
    )
    destination = fields.Selection(
        LOCATIONS,
        string='الوجهة',
        required=True,
    )
    passengers_count = fields.Integer(string='عدد الركاب')

    # العداد
    odometer_start = fields.Float(string='العداد قبل التحرك')
    odometer_end = fields.Float(string='العداد بعد الرجوع')
    distance = fields.Float(
        string='عدد الكيلومترات',
        compute='_compute_distance',
        store=True,
    )

    # الوقود
    fuel_consumed = fields.Float(string='كمية الوقود المستهلك (لتر)')
    fuel_price = fields.Float(string='سعر اللتر')
    fuel_station = fields.Char(string='محطة البنزين')
    fuel_total = fields.Float(
        string='إجمالي تكلفة الوقود',
        compute='_compute_fuel_total',
        store=True,
    )

    state = fields.Selection(
        [
            ('draft', 'مسودة'),
            ('confirmed', 'مؤكدة'),
            ('done', 'منتهية'),
            ('cancelled', 'ملغاة'),
        ],
        string='حالة الرحلة',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )
    note = fields.Text(string='ملاحظات')

    handover_id = fields.Many2one(
        'vehicle.handover',
        string='الصيانة قبل الاستلام',
        copy=False,
        readonly=True,
    )

    # ------------------------------------------------------------------
    # الترقيم التلقائي
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'جديد':
                vals['name'] = self.env['ir.sequence'].next_by_code('trip.order') or 'جديد'
        records = super().create(vals_list)
        # ربط الصيانة قبل الاستلام بالرحلة (لو الرحلة اتفتحت من الصيانة)
        for rec in records:
            if rec.handover_id and not rec.handover_id.trip_id:
                rec.handover_id.trip_id = rec
        return records

    # ------------------------------------------------------------------
    # الحسابات
    # ------------------------------------------------------------------
    @api.depends('odometer_start', 'odometer_end')
    def _compute_distance(self):
        for rec in self:
            if rec.odometer_end:
                rec.distance = rec.odometer_end - rec.odometer_start
            else:
                rec.distance = 0.0

    @api.depends('fuel_consumed', 'fuel_price')
    def _compute_fuel_total(self):
        for rec in self:
            rec.fuel_total = rec.fuel_consumed * rec.fuel_price

    # ------------------------------------------------------------------
    # التوفر حسب المواعيد
    # ------------------------------------------------------------------
    def _overlapping_trips(self, field_name, resource):
        """رحلات مؤكدة تانية على نفس العربية/السائق وبتتقاطع مع مواعيد الرحلة دي."""
        self.ensure_one()
        return self.search([
            ('id', '!=', self._origin.id or 0),
            (field_name, '=', resource.id),
            ('state', '=', 'confirmed'),
            ('departure_datetime', '<', self.arrival_datetime),
            ('arrival_datetime', '>', self.departure_datetime),
        ])

    def _day_bounds_utc(self, day):
        """بداية ونهاية اليوم بتوقيت المستخدم، محوّلين لـ UTC (زي ما بتتخزن المواعيد)."""
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        start = tz.localize(datetime.combine(day, time.min))
        end = tz.localize(datetime.combine(day, time.max))
        return (start.astimezone(pytz.utc).replace(tzinfo=None),
                end.astimezone(pytz.utc).replace(tzinfo=None))

    def _availability_window(self):
        """الفترة اللي بنفلتر عليها: وقتي التحرك والوصول لو مكتوبين،
        وإلا يوم تاريخ الرحلة كله."""
        self.ensure_one()
        if self.departure_datetime and self.arrival_datetime:
            return self.departure_datetime, self.arrival_datetime
        if self.trip_date:
            return self._day_bounds_utc(self.trip_date)
        return False, False

    @api.depends('departure_datetime', 'arrival_datetime', 'trip_date',
                 'state', 'vehicle_id', 'driver_id')
    def _compute_available_resources(self):
        Vehicle = self.env['vehicle.vehicle']
        Driver = self.env['driver.profile']
        for rec in self:
            start, end = rec._availability_window()
            if start and end:
                # الفترة معروفة: العربية المتاحة هي اللي مفيش عليها رحلة
                # مؤكدة بتتقاطع مع الفترة دي (حتى لو حالتها "في رحلة" دلوقتي)
                busy = self.search([
                    ('id', '!=', rec._origin.id or 0),
                    ('state', '=', 'confirmed'),
                    ('departure_datetime', '<', end),
                    ('arrival_datetime', '>', start),
                ])
                vehicles = Vehicle.search([
                    ('state', 'not in', VEHICLE_BLOCKED_STATES),
                    ('id', 'not in', busy.vehicle_id.ids),
                ])
                drivers = Driver.search([
                    ('state', 'not in', DRIVER_BLOCKED_STATES),
                    ('id', 'not in', busy.driver_id.ids),
                ])
            else:
                # مفيش تاريخ ولا مواعيد: نعرض المتاحين دلوقتي بس
                vehicles = Vehicle.search([('state', '=', 'available')])
                drivers = Driver.search([('state', '=', 'available')])
            # القيمة المختارة حالياً تفضل ظاهرة
            rec.available_vehicle_ids = vehicles | rec.vehicle_id
            rec.available_driver_ids = drivers | rec.driver_id

    # ------------------------------------------------------------------
    # التحقق من البيانات
    # ------------------------------------------------------------------
    @api.constrains('departure_datetime', 'arrival_datetime')
    def _check_datetimes(self):
        for rec in self:
            if (rec.departure_datetime and rec.arrival_datetime
                    and rec.arrival_datetime < rec.departure_datetime):
                raise ValidationError(_('وقت الوصول لازم يكون بعد وقت التحرك.'))

    @api.constrains('odometer_start', 'odometer_end')
    def _check_odometer(self):
        for rec in self:
            if rec.odometer_end and rec.odometer_end < rec.odometer_start:
                raise ValidationError(_('العداد بعد الرجوع لا يمكن أن يكون أقل من العداد قبل التحرك.'))

    @api.constrains('handover_id', 'vehicle_id', 'driver_id')
    def _check_handover_match(self):
        for rec in self:
            h = rec.handover_id
            if h and (h.vehicle_id != rec.vehicle_id or h.driver_id != rec.driver_id):
                raise ValidationError(_('العربية والسائق لازم يكونوا نفس البيانات في الصيانة قبل الاستلام.'))

    @api.constrains('passengers_count', 'fuel_consumed', 'fuel_price')
    def _check_negative_values(self):
        for rec in self:
            if rec.passengers_count < 0 or rec.fuel_consumed < 0 or rec.fuel_price < 0:
                raise ValidationError(_('لا يمكن إدخال قيم سالبة.'))

    # ------------------------------------------------------------------
    # عدد الركاب (بيتاخد من عدد مقاعد العربية ومينفعش يزيد عنه)
    # ------------------------------------------------------------------
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id_passengers(self):
        """أول ما تختاري العربية، عدد الركاب بيتملى بعدد مقاعدها."""
        if self.vehicle_id:
            self.passengers_count = self.vehicle_id.seats_count

    @api.onchange('passengers_count')
    def _onchange_passengers_count(self):
        seats = self.vehicle_id.seats_count
        if self.vehicle_id and self.passengers_count > seats:
            self.passengers_count = seats
            return {
                'warning': {
                    'title': _('عدد الركاب'),
                    'message': _('عدد ركاب العربية (%s) لا يمكن استخدام عدد أكبر') % seats,
                }
            }

    @api.constrains('passengers_count', 'vehicle_id')
    def _check_passengers_capacity(self):
        for rec in self:
            seats = rec.vehicle_id.seats_count
            if rec.vehicle_id and rec.passengers_count > seats:
                raise ValidationError(
                    _('عدد ركاب العربية (%s) لا يمكن استخدام عدد أكبر') % seats)

    # ------------------------------------------------------------------
    # العداد قبل التحرك = العداد بعد الرجوع في آخر رحلة سابقة للعربية
    # ------------------------------------------------------------------
    def _get_previous_odometer_end(self):
        """العداد بعد الرجوع في آخر رحلة سابقة (مؤكدة أو منتهية) لنفس العربية."""
        self.ensure_one()
        if not self.vehicle_id:
            return 0.0
        domain = [
            ('vehicle_id', '=', self.vehicle_id.id),
            ('id', '!=', self._origin.id or 0),
            ('state', 'in', ('confirmed', 'done')),
            ('odometer_end', '>', 0),
        ]
        if self.departure_datetime:
            domain.append(('departure_datetime', '<=', self.departure_datetime))
        previous = self.search(
            domain, order='departure_datetime desc, id desc', limit=1)
        return previous.odometer_end

    @api.onchange('vehicle_id', 'departure_datetime')
    def _onchange_vehicle_odometer(self):
        if self.vehicle_id and self.state == 'draft':
            last_end = self._get_previous_odometer_end()
            if last_end:
                self.odometer_start = last_end

    # ------------------------------------------------------------------
    # حالة السائق والعربية
    # ------------------------------------------------------------------
    def _is_started(self):
        """الرحلة بدأت فعلاً (وقت التحرك جه)؟"""
        self.ensure_one()
        return (not self.departure_datetime
                or self.departure_datetime <= fields.Datetime.now())

    def _set_resources_on_trip(self):
        """يخلي السائق والعربية (في رحلة) لو الرحلة بدأت فعلاً.
        الرحلات المستقبلية بتفضل العربية والسائق متاحين لحد وقت التحرك
        (الـ cron بيحدّثهم وقتها)."""
        for rec in self:
            if rec._is_started():
                if rec.driver_id.state == 'available':
                    rec.driver_id.state = 'on_trip'
                if rec.vehicle_id.state == 'available':
                    rec.vehicle_id.state = 'on_trip'

    def _release_resources(self):
        """يرجع السائق والعربية متاحين لو مفيش عندهم رحلة تانية شغالة دلوقتي."""
        now = fields.Datetime.now()
        for rec in self:
            for field_name in ('driver_id', 'vehicle_id'):
                resource = rec[field_name]
                if resource and resource.state == 'on_trip':
                    running = self.search_count([
                        (field_name, '=', resource.id),
                        ('state', '=', 'confirmed'),
                        ('id', '!=', rec.id),
                        ('departure_datetime', '<=', now),
                    ])
                    if not running:
                        resource.state = 'available'

    @api.model
    def _cron_sync_trip_states(self):
        """بيشغّل حالة (في رحلة) للرحلات المؤكدة اللي وقت تحركها جه."""
        trips = self.search([
            ('state', '=', 'confirmed'),
            ('departure_datetime', '<=', fields.Datetime.now()),
        ])
        trips._set_resources_on_trip()

    # ------------------------------------------------------------------
    # الأزرار
    # ------------------------------------------------------------------
    def action_open_handover(self):
        """يحفظ الرحلة (الزر بيحفظ تلقائي) ويفتح الصيانة قبل الاستلام."""
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('صيانة قبل الاستلام'),
            'res_model': 'vehicle.handover',
            'view_mode': 'form',
            'target': 'current',
        }
        if self.handover_id:
            action['res_id'] = self.handover_id.id
        else:
            action['context'] = {
                'default_vehicle_id': self.vehicle_id.id,
                'default_driver_id': self.driver_id.id,
                'default_odometer': self.odometer_start,
                'default_trip_id': self.id,
            }
        return action

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.handover_id:
                raise UserError(_('لازم يتم عمل الصيانة قبل الاستلام قبل تأكيد الرحلة.'))
            if rec.driver_id.state in DRIVER_BLOCKED_STATES:
                raise UserError(_('السائق "%s" غير متاح (خارج الخدمة أو موقوف).') % rec.driver_id.display_name)
            if rec.vehicle_id.state in VEHICLE_BLOCKED_STATES:
                raise UserError(_('العربية "%s" خارج الخدمة.') % rec.vehicle_id.display_name)
            if rec.departure_datetime and rec.arrival_datetime:
                if rec._overlapping_trips('vehicle_id', rec.vehicle_id):
                    raise UserError(_('العربية دي عليها رحلة مؤكدة تانية في نفس الوقت.'))
                if rec._overlapping_trips('driver_id', rec.driver_id):
                    raise UserError(_('السائق ده عليه رحلة مؤكدة تانية في نفس الوقت.'))
            rec.state = 'confirmed'
            rec._set_resources_on_trip()

    def action_done(self):
        for rec in self:
            if rec.state != 'confirmed':
                continue
            if not rec.odometer_end:
                raise UserError(_('اكتبي العداد بعد الرجوع قبل إنهاء الرحلة.'))
            rec.state = 'done'
            rec._release_resources()

    def action_cancel(self):
        for rec in self:
            if rec.state in ('draft', 'confirmed'):
                rec.state = 'cancelled'
                rec._release_resources()

    def action_draft(self):
        for rec in self:
            if rec.state in ('confirmed', 'cancelled'):
                rec.state = 'draft'
                rec._release_resources()