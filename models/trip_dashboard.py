# -*- coding: utf-8 -*-
"""لوحة المعلومات: دوال رسم الـ HTML + موديل الـ Dashboard في ملف واحد."""
from html import escape

from markupsafe import Markup

from odoo import api, fields, models, _

PURPLE = '#714B67'
GREEN = '#28a745'
BLUE = '#17a2b8'
ORANGE = '#fd7e14'
RED = '#dc3545'
GRAY = '#6c757d'

BOX = ('background:var(--o-view-background-color,#fff);'
       'border:1px solid rgba(0,0,0,.12);border-radius:8px;padding:14px 16px;')
GRID = 'display:grid;gap:14px;margin-top:14px;grid-template-columns:%s;'


def _e(value):
    return escape(str(value if value is not None else ''), quote=True)


def fmt(value, decimals=0):
    return '{:,.{d}f}'.format(value or 0, d=decimals)


def _grid(min_width, inner):
    cols = 'repeat(auto-fit,minmax(%dpx,1fr))' % min_width
    return '<div style="%s">%s</div>' % (GRID % cols, inner)


DETAIL_LIMIT = 50


def _card(label, value, sub='', color=PURPLE, icon='fa-circle', key=''):
    """key = اسم القايمة اللي تفتح تحت الكروت لما الكارت يتضغط (JS في static)."""
    return (
        '<div class="o_trip_card" data-detail="%s" data-color="%s" '
        'style="%sborder-inline-start:5px solid %s;cursor:pointer;'
        'transition:box-shadow .15s;">'
        '<div style="font-size:12px;opacity:.7;"><i class="fa %s me-1"></i>%s</div>'
        '<div style="font-size:26px;font-weight:700;line-height:1.3;">%s</div>'
        '<div style="font-size:12px;opacity:.65;">%s</div></div>'
    ) % (_e(key), color, BOX, color, icon, _e(label), _e(value), _e(sub))


def _detail_table(headers, rows):
    """rows = قايمة صفوف، كل صف قايمة قيم عادية (بتتعمل escape هنا)."""
    if not rows:
        return _empty()
    shown = rows[:DETAIL_LIMIT]
    body = ''.join(
        '<tr>%s</tr>' % ''.join('<td>%s</td>' % _e(c) for c in r)
        for r in shown)
    note = ''
    if len(rows) > DETAIL_LIMIT:
        note = ('<div style="font-size:11px;opacity:.65;margin-top:6px;">'
                'معروض أول %d من %d</div>' % (DETAIL_LIMIT, len(rows)))
    return (
        '<div style="overflow-x:auto;max-height:320px;overflow-y:auto;">'
        '<table class="table table-sm" style="margin:0;">'
        '<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>%s' % (
            ''.join('<th>%s</th>' % _e(h) for h in headers), body, note)
    )


def _detail_panel(key, title, body, color=PURPLE):
    return (
        '<div class="o_trip_detail" data-detail-for="%s" '
        'style="%sdisplay:none;margin-top:14px;border-top:3px solid %s;">'
        '<div style="font-weight:700;margin-bottom:10px;">%s</div>%s</div>'
    ) % (_e(key), BOX, color, _e(title), body)


def _details(data, cur):
    t = data['totals']
    trips = data['trip_rows']
    counted = [r for r in trips if r['counted']]
    return ''.join([
        _detail_panel('trips', 'تفاصيل الرحلات', _detail_table(
            ['الرحلة', 'التاريخ', 'العربية', 'السائق', 'الوجهة', 'الحالة'],
            [[r['name'], r['date'], r['vehicle'], r['driver'],
              r['destination'], r['state']] for r in trips]), PURPLE),
        _detail_panel('km', 'الكيلومترات لكل رحلة', _detail_table(
            ['الرحلة', 'التاريخ', 'العربية', 'كم'],
            [[r['name'], r['date'], r['vehicle'], fmt(r['km'])]
             for r in counted]), BLUE),
        _detail_panel('passengers', 'الركاب لكل رحلة', _detail_table(
            ['الرحلة', 'التاريخ', 'السائق', 'الركاب'],
            [[r['name'], r['date'], r['driver'], r['passengers']]
             for r in counted]), GREEN),
        _detail_panel('fuel', 'تكلفة الوقود لكل رحلة', _detail_table(
            ['الرحلة', 'التاريخ', 'العربية', 'لتر', 'التكلفة'],
            [[r['name'], r['date'], r['vehicle'], fmt(r['fuel_liters']),
              fmt(r['fuel_cost']) + cur] for r in counted]), ORANGE),
        _detail_panel('maint', 'عمليات الصيانة', _detail_table(
            ['العملية', 'التاريخ', 'العربية', 'النوع', 'التكلفة'],
            [[r['name'], r['date'], r['vehicle'], r['type'],
              fmt(r['cost']) + cur] for r in data['maint_rows']]), RED),
        _detail_panel('total', 'مكونات إجمالي التكاليف', _detail_table(
            ['البند', 'القيمة'],
            [['تكلفة الوقود', fmt(t['fuel_cost']) + cur],
             ['تكلفة الصيانة', fmt(t['maint_cost']) + cur],
             ['الإجمالي', fmt(t['total_cost']) + cur],
             ['إجمالي الكيلومترات', fmt(t['km']) + ' كم'],
             ['التكلفة لكل كم', fmt(t['cost_per_km'], 2) + cur]]), GRAY),
        _detail_panel('handover', 'فحوصات الصيانة قبل الاستلام', _detail_table(
            ['التاريخ', 'العربية', 'بنود (لا)', 'إجمالي البنود'],
            [[r['date'], r['vehicle'], r['failed'], r['checks']]
             for r in data['handover_rows']]), BLUE),
    ])


def _box(title, body, icon='fa-bar-chart'):
    return (
        '<div style="%s"><div style="font-weight:700;margin-bottom:10px;">'
        '<i class="fa %s me-1" style="color:%s"></i>%s</div>%s</div>'
    ) % (BOX, icon, PURPLE, _e(title), body)


def _empty():
    return '<div style="opacity:.55;padding:8px 0;">لا توجد بيانات في هذه الفترة</div>'


def _bars(rows, color=PURPLE):
    """rows = [(الاسم، القيمة الرقمية، النص المعروض، تفاصيل)]"""
    if not rows:
        return _empty()
    top = max(r[1] for r in rows) or 1
    out = []
    for label, value, shown, sub in rows:
        width = max(4, int(value * 100 / top)) if value else 0
        out.append(
            '<div style="margin-bottom:11px;">'
            '<div style="display:flex;justify-content:space-between;gap:8px;">'
            '<span>%s</span><b>%s</b></div>'
            '<div style="background:rgba(0,0,0,.08);border-radius:4px;height:8px;">'
            '<div style="width:%d%%;background:%s;height:8px;border-radius:4px;"></div></div>'
            '<div style="font-size:11px;opacity:.65;">%s</div></div>'
            % (_e(label), _e(shown), width, color, _e(sub))
        )
    return ''.join(out)


def _trend(rows):
    if not rows:
        return _empty()
    top = max(r['trips'] for r in rows) or 1
    cols = []
    for r in rows:
        height = max(4, int(r['trips'] * 110 / top))
        cols.append(
            '<div style="flex:1;min-width:34px;text-align:center;">'
            '<div style="font-size:12px;font-weight:700;">%s</div>'
            '<div style="height:%dpx;background:%s;border-radius:4px 4px 0 0;"></div>'
            '<div style="font-size:10px;opacity:.7;">%s</div></div>'
            % (r['trips'], height, PURPLE, _e(r['name']))
        )
    return ('<div style="display:flex;align-items:flex-end;gap:6px;'
            'overflow-x:auto;">%s</div>' % ''.join(cols))


def _status_line(label, count, color):
    return (
        '<div style="display:flex;justify-content:space-between;padding:4px 0;">'
        '<span><i class="fa fa-circle me-1" style="color:%s;font-size:10px;"></i>%s</span>'
        '<b>%s</b></div>' % (color, _e(label), count)
    )


def _alerts_table(alerts, upcoming):
    rows = []
    for a in alerts:
        expired = a['status'] == 'expired'
        rows.append(
            '<tr><td>%s</td><td>%s</td><td>%s</td>'
            '<td style="color:%s;font-weight:700;">%s</td></tr>' % (
                _e(a['kind']), _e(a['who']), _e(a['date']),
                RED if expired else ORANGE,
                'منتهية منذ %d يوم' % abs(a['days']) if expired
                else 'تنتهي خلال %d يوم' % a['days'])
        )
    for u in upcoming:
        late = u['days'] < 0
        rows.append(
            '<tr><td>صيانة قادمة</td><td>%s</td><td>%s</td>'
            '<td style="color:%s;font-weight:700;">%s</td></tr>' % (
                _e(u['who']), _e(u['date']),
                RED if late else ORANGE,
                'متأخرة %d يوم' % abs(u['days']) if late
                else 'خلال %d يوم' % u['days'])
        )
    if not rows:
        return '<div style="opacity:.6;">لا توجد تنبيهات 👌</div>'
    return (
        '<table class="table table-sm" style="margin:0;">'
        '<thead><tr><th>النوع</th><th>العربية / السائق</th><th>التاريخ</th>'
        '<th>الحالة</th></tr></thead><tbody>%s</tbody></table>' % ''.join(rows)
    )


def render_dashboard(data, period_label, currency=''):
    t = data['totals']
    cur = ' ' + currency if currency else ''

    cards = ''.join([
        _card('إجمالي الرحلات', t['trips_all'],
              'مؤكدة %s • منتهية %s • ملغاة %s' % (
                  t['confirmed'], t['done'], t['cancelled']),
              PURPLE, 'fa-road', 'trips'),
        _card('إجمالي الكيلومترات', fmt(t['km']), 'كم', BLUE, 'fa-tachometer',
              'km'),
        _card('عدد الركاب', fmt(t['passengers']), 'راكب', GREEN, 'fa-users',
              'passengers'),
        _card('تكلفة الوقود', fmt(t['fuel_cost']) + cur,
              '%s لتر' % fmt(t['fuel_liters']), ORANGE, 'fa-tint', 'fuel'),
        _card('تكلفة الصيانة', fmt(t['maint_cost']) + cur,
              '%s عملية صيانة' % t['maint_count'], RED, 'fa-wrench',
              'maint'),
        _card('إجمالي التكاليف', fmt(t['total_cost']) + cur,
              '%s لكل كم' % fmt(t['cost_per_km'], 2), GRAY, 'fa-money',
              'total'),
        _card('صيانة قبل الاستلام', t['handover_count'], 'فحص', BLUE,
              'fa-clipboard', 'handover'),
    ])

    fleet, crew = data['fleet'], data['crew']
    status_box = _box('حالة العربيات والسواقين', (
        '<div style="font-weight:700;margin-bottom:4px;">العربيات (%s)</div>' % fleet['total']
        + _status_line('متاحة', fleet['available'], GREEN)
        + _status_line('في رحلة', fleet['on_trip'], BLUE)
        + _status_line('خارج الخدمة', fleet['out_of_service'], RED)
        + '<div style="font-weight:700;margin:10px 0 4px;">السواقين (%s)</div>' % crew['total']
        + _status_line('متاح', crew['available'], GREEN)
        + _status_line('في رحلة', crew['on_trip'], BLUE)
        + _status_line('خارج الخدمة', crew['off'], ORANGE)
        + _status_line('موقوف', crew['suspended'], RED)
    ), 'fa-heartbeat')

    veh_box = _box('أكتر العربيات رحلات', _bars(
        [(r['name'], r['trips'], '%s رحلة' % r['trips'],
          '%s كم' % fmt(r['km'])) for r in data['top_vehicles']]), 'fa-car')

    drv_box = _box('أكتر السواقين شغلاً', _bars(
        [(r['name'], r['trips'], '%s رحلة' % r['trips'],
          '%s كم • %s راكب' % (fmt(r['km']), r['passengers']))
         for r in data['top_drivers']], BLUE), 'fa-id-card')

    maint_box = _box('أكتر العربيات صيانة وتكلفة', _bars(
        [(r['name'], r['cost'], fmt(r['cost']) + cur,
          '%s عملية صيانة' % r['count']) for r in data['top_maint']],
        RED), 'fa-wrench')

    types_box = _box('تكلفة الصيانة حسب النوع', _bars(
        [(r['name'], r['cost'], fmt(r['cost']) + cur, '')
         for r in data['maint_types']], ORANGE), 'fa-cogs')

    handover_box = _box('صيانة قبل الاستلام: أكتر عربية فيها بنود (لا)', _bars(
        [(r['name'], r['failed'], '%s بند' % r['failed'],
          '%s فحص' % r['count']) for r in data['top_handover']],
        GRAY), 'fa-clipboard')

    dest_box = _box('أكتر الوجهات طلباً', _bars(
        [(r['name'], r['trips'], '%s رحلة' % r['trips'], '')
         for r in data['destinations']], GREEN), 'fa-map-marker')

    trend_box = _box('الرحلات شهر بشهر', _trend(data['monthly']), 'fa-line-chart')

    alerts_box = _box('تنبيهات الرخص والتأمين والصيانة القادمة',
                      _alerts_table(data['alerts'], data['upcoming']),
                      'fa-bell')

    html = (
        '<div class="o_trip_dash" dir="rtl" style="text-align:right;">'
        '<div style="font-size:15px;margin-bottom:4px;">'
        '<i class="fa fa-calendar me-1"></i>الفترة: <b>%s</b></div>' % _e(period_label)
        + _grid(190, cards)
        + _details(data, cur)
        + _grid(300, veh_box + drv_box + status_box)
        + _grid(300, maint_box + types_box + handover_box)
        + _grid(300, dest_box + trend_box)
        + _grid(420, alerts_box)
        + '</div>'
    )
    return Markup(html)


class TripDashboard(models.TransientModel):
    """شاشة الـ Dashboard. الأرقام بتتحسب من البيانات الحقيقية كل مرة تتفتح."""
    _name = 'trip.dashboard'
    _inherit = ['trip.period.mixin']
    _description = 'لوحة المعلومات'

    period_type = fields.Selection(
        [('month', 'شهر محدد'), ('all', 'كل الفترات')],
        string='الفترة', default='month', required=True,
    )
    dashboard_html = fields.Html(
        compute='_compute_dashboard_html', sanitize=False)

    @api.model
    def action_open_dashboard(self):
        rec = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'name': _('لوحة المعلومات'),
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_range(self):
        self.ensure_one()
        if self.period_type == 'all' or not (self.month and self.year):
            return False, False
        return self._month_range()

    def _period_label(self):
        self.ensure_one()
        if self.period_type == 'all' or not (self.month and self.year):
            return _('كل الفترات')
        return self._month_label()

    @api.depends('period_type', 'month', 'year')
    def _compute_dashboard_html(self):
        stats = self.env['trip.stats']
        currency = self.env.company.currency_id.symbol or ''
        for rec in self:
            date_from, date_to = rec._get_range()
            data = stats.get_data(date_from, date_to)
            rec.dashboard_html = render_dashboard(
                data, rec._period_label(), currency)

    def action_refresh(self):
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_print_monthly(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('طباعة تقرير شهري'),
            'res_model': 'trip.monthly.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_month': self.month,
                'default_year': self.year,
            },
        }