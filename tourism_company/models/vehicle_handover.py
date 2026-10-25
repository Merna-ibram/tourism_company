# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

HANDOVER_ITEMS = [
    "كشف على مقاعد زيت المحرك",
    "كشف على مقاعد زيت التبريد",
    "كشف على مقاعد زيت البود",
    "كشف على سيرة التشغيل وشد إذا لزم الأمر",
    "تنظيف فلتر هواء",
    "مراجعة زيت المحرك - ملية دينامو - عداد حرارة - زيوت",
    "كشف على اجهزة التبريد (حوض - قاعدة)",
    "الكشف على التكييف",
    "كشف على مستوى مياه المساحات",
    "الكشف على السماعات واللايك",
    "الكشف على الأبواب صعود ونزول",
    "الكشف على مكابح اليد (هاند بريلك)",
    "الكشف على لمبة الصيانات",
    "الكشف على عوادم السيارة",
    "الكشف على كلاكس السيارة",
    "الكشف على الثلاجة",
    "مناديل جافة ومناديل مبللة",
    "مياة ومشروبات غازية",
    "شنطة الإسعافات",
    "النظافة الداخلية",
    "النظافة الخارجية",
    "الأنوار الأمامية والخلفية والداخلية والاشارات والشاوة",
    "الكشف على عجل السيارة وارتفاعه",
    "الكشف على مرايات السيارة",
]


class VehicleHandover(models.Model):
    _name = 'vehicle.handover'
    _description = 'صيانة قبل الاستلام'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    def _default_lines(self):
        return [
            (0, 0, {'sequence': i, 'name': name})
            for i, name in enumerate(HANDOVER_ITEMS, 1)
        ]

    name = fields.Char(string='المرجع', compute='_compute_name', store=True)
    vehicle_id = fields.Many2one(
        'vehicle.vehicle', string='رقم السيارة', required=True, tracking=True,
        ondelete='restrict',
        domain=[('state', '=', 'available')],
    )
    # True لما الشاشة تتفتح من داخل العربية، فتتقفل خانة العربية
    vehicle_locked = fields.Boolean(
        string='السيارة مقفولة', store=False,
        default=lambda self: bool(self.env.context.get('default_vehicle_id')),
    )
    driver_id = fields.Many2one(
        'driver.profile', string='اسم السائق', required=True, tracking=True,
        domain=[('state', '=', 'available')],
    )
    odometer = fields.Integer(string='العداد', tracking=True)
    date = fields.Date(
        string='اليوم', required=True, default=fields.Date.context_today,
    )
    fuel_level = fields.Selection(
        [('e', 'فارغ (E)'), ('q1', '1/4'), ('h', '1/2'),
         ('q3', '3/4'), ('f', 'ممتلئ (F)')],
        string='مستوى الوقود',
    )
    line_ids = fields.One2many(
        'vehicle.handover.line', 'handover_id', string='بنود الصيانة',
        default=_default_lines,
    )
    note = fields.Text(string='ملاحظات عامة')

    @api.depends('vehicle_id.plate_number', 'date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s - %s' % (
                rec.vehicle_id.plate_number or '', rec.date or '')

    @api.constrains('line_ids')
    def _check_all_lines_answered(self):
        """لازم كل بند يتعلّم عليه (نعم) أو (لا). الملاحظات اختيارية."""
        for rec in self:
            missing = rec.line_ids.filtered(
                lambda l: not l.is_yes and not l.is_no)
            if missing:
                items = '\n'.join(
                    '%s - %s' % (l.sequence, l.name)
                    for l in missing.sorted('sequence')
                )
                raise ValidationError(
                    _('لازم تختار (نعم) أو (لا) لكل البنود قبل الحفظ.\n'
                      'البنود الناقصة:\n%s') % items
                )
            both = rec.line_ids.filtered(lambda l: l.is_yes and l.is_no)
            if both:
                raise ValidationError(
                    _('لا يمكن اختيار (نعم) و(لا) معاً في نفس البند: %s')
                    % both[0].name
                )

    def write(self, vals):
        if 'vehicle_id' in vals:
            for rec in self:
                if rec.vehicle_id.id != vals['vehicle_id']:
                    raise UserError(_('لا يمكن تغيير السيارة بعد الحفظ.'))
        return super().write(vals)


class VehicleHandoverLine(models.Model):
    _name = 'vehicle.handover.line'
    _description = 'بند صيانة قبل الاستلام'
    _order = 'sequence, id'

    handover_id = fields.Many2one(
        'vehicle.handover', required=True, ondelete='cascade')
    sequence = fields.Integer(string='م', default=10)
    name = fields.Char(string='البند', required=True)
    is_yes = fields.Boolean(string='نعم')
    is_no = fields.Boolean(string='لا')
    note = fields.Char(string='ملاحظات')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                idx = (vals.get('sequence') or 0) - 1
                if 0 <= idx < len(HANDOVER_ITEMS):
                    vals['name'] = HANDOVER_ITEMS[idx]
                else:
                    vals['name'] = _('بند')
        return super().create(vals_list)

    @api.onchange('is_yes')
    def _onchange_is_yes(self):
        if self.is_yes:
            self.is_no = False

    @api.onchange('is_no')
    def _onchange_is_no(self):
        if self.is_no:
            self.is_yes = False