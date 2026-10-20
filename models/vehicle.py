import logging
import re
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class VehicleVehicle(models.Model):
  _name = 'vehicle.vehicle'
  _description = 'سيارة'
  _inherit = ['mail.thread', 'mail.activity.mixin']
  _rec_name = 'plate_number'
  _order = 'plate_number'

  plate_number = fields.Char(
      string='رقم العربية', required=True, tracking=True, copy=False
  )
  vehicle_type = fields.Selection(
      [
          ('car', 'ملاكي'),
          ('suv', 'دفع رباعي'),
          ('van', 'فان'),
          ('minibus', 'ميني باص'),
          ('bus', 'أتوبيس'),
          ('truck', 'شاحنة نقل'),
          ('motorcycle', 'دراجة نارية'),
          ('scooter', 'سكوتر'),
          ('limousine', 'ليموزين'),
          ('other', 'أخرى'),
      ],
      string='نوع السيارة',
      required=True,
      default='car',
      tracking=True,
  )
  manufacture_year = fields.Char(
      string='سنة التصنيع', size=4, required=True, tracking=True
  )
  model_name = fields.Char(string='الموديل', required=True)
  color = fields.Selection(
      [
          ('white', 'أبيض'),
          ('black', 'أسود'),
          ('silver', 'فضّي'),
          ('gray', 'رمادي / فيراني'),
          ('blue', 'أزرق / كحلي'),
          ('red', 'أحمر / نبيتي'),
          ('champagne', 'شامبين / ذهبي'),
          ('brown', 'بني'),
          ('green', 'أخضر'),
          ('other', 'لون آخر'),
      ],
      string='اللون',
      required=True,
      default='black',
  )
  seats_count = fields.Integer(string='عدد المقاعد', required=True, default=4)
  chassis_number = fields.Char(string='رقم الشاسيه', required=True, copy=False)
  motor_number = fields.Char(string='رقم الموتور', required=True, copy=False)
  purchase_date = fields.Date(string='تاريخ الشراء', required=True)
  driver_name = fields.Char(string='اسم السائق', tracking=True)
  active = fields.Boolean(default=True)

  state = fields.Selection(
      [
          ('available', 'متاحة'),
          ('on_trip', 'في رحلة'),
          ('out_of_service', 'خارج الخدمة'),
      ],
      string='حالة العربية',
      default='available',
      required=True,
      tracking=True,
  )
  is_available = fields.Boolean(
      string='متاحة (Available)',
      compute='_compute_state_flags',
      inverse='_inverse_is_available',
  )
  is_on_trip = fields.Boolean(
      string='في رحلة (On trip)',
      compute='_compute_state_flags',
      inverse='_inverse_is_on_trip',
  )
  is_out_of_service = fields.Boolean(
      string='خارج الخدمة (Out of service)',
      compute='_compute_state_flags',
      inverse='_inverse_is_out_of_service',
  )

  license_number = fields.Char(string='رقم الرخصة', required=True, tracking=True)
  license_issue_date = fields.Date(
      string='تاريخ إصدار الرخصة', required=True
  )
  license_expiry_date = fields.Date(
      string='تاريخ انتهاء الرخصة', required=True, tracking=True
  )
  license_days_left = fields.Integer(
      string='الأيام المتبقية على انتهاء الرخصة',
      compute='_compute_license_alert',
  )
  license_alert_state = fields.Selection(
      [('ok', 'سارية'), ('soon', 'تنتهي قريباً'), ('expired', 'منتهية')],
      string='حالة الرخصة',
      compute='_compute_license_alert',
  )
  license_notified = fields.Boolean(
      string='تم تنبيه الرخصة', default=False, copy=False
  )

  insurance_company = fields.Char(string='شركة التأمين', required=True)
  insurance_number = fields.Char(
      string='رقم وثيقة التأمين', required=True, tracking=True
  )
  insurance_start_date = fields.Date(
      string='تاريخ بداية التأمين', required=True
  )
  insurance_expiry_date = fields.Date(
      string='تاريخ انتهاء التأمين', required=True, tracking=True
  )
  insurance_days_left = fields.Integer(
      string='الأيام المتبقية على انتهاء التأمين',
      compute='_compute_insurance_alert',
  )
  insurance_alert_state = fields.Selection(
      [('ok', 'ساري'), ('soon', 'ينتهي قريباً'), ('expired', 'منتهي')],
      string='حالة التأمين',
      compute='_compute_insurance_alert',
  )
  insurance_notified = fields.Boolean(
      string='تم تنبيه التأمين', default=False, copy=False
  )

  maintenance_ids = fields.One2many(
      'vehicle.maintenance', 'vehicle_id', string='الصيانة الشهرية'
  )
  maintenance_count = fields.Integer(
      string='عدد الصيانات', compute='_compute_maintenance_count'
  )
  handover_count = fields.Integer(
      string='صيانة قبل الاستلام', compute='_compute_handover_count'
  )

  _sql_constraints = [
      (
          'plate_number_uniq',
          'unique(plate_number)',
          'رقم العربية موجود بالفعل، ولازم يكون مختلف لكل عربية!',
      ),
      (
          'chassis_number_uniq',
          'unique(chassis_number)',
          'رقم الشاسيه موجود بالفعل!',
      ),
      ('motor_number_uniq', 'unique(motor_number)', 'رقم الموتور موجود بالفعل!'),
  ]

  @api.constrains('manufacture_year')
  def _check_manufacture_year(self):
    current_year = date.today().year
    for rec in self:
      if rec.manufacture_year:
        if not re.fullmatch(r'[0-9]{4}', rec.manufacture_year):
          raise ValidationError(
              _('سنة التصنيع لازم تكون 4 أرقام صحيحة فقط بدون حروف (مثال: 2024).')
          )

        year_int = int(rec.manufacture_year)
        if not (1900 <= year_int <= current_year + 1):
          raise ValidationError(
              _('سنة التصنيع لازم تكون بين 1900 و %s.') % (current_year + 1)
          )

  @api.onchange('manufacture_year')
  def _onchange_manufacture_year(self):
    """ينظف القيمة أثناء الكتابة: يحول الأرقام العربية لإنجليزية ويحذف أي حرف أو رمز ويقص عند 4 خانات."""
    if self.manufacture_year:
      arabic_digits = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
      value = self.manufacture_year.translate(arabic_digits)
      self.manufacture_year = re.sub(r'[^0-9]', '', value)[:4]

  @api.constrains('seats_count')
  def _check_seats_count(self):
    for rec in self:
      if rec.seats_count and not (1 <= rec.seats_count <= 999):
        raise ValidationError(
            _('عدد المقاعد لازم يكون رقم من 1 إلى 999 (3 خانات كحد أقصى).')
        )

  @api.constrains('license_issue_date', 'license_expiry_date')
  def _check_license_dates(self):
    for rec in self:
      if (
          rec.license_issue_date
          and rec.license_expiry_date
          and rec.license_expiry_date < rec.license_issue_date
      ):
        raise ValidationError(
            _('تاريخ انتهاء الرخصة لازم يكون بعد تاريخ الإصدار.')
        )

  @api.constrains('insurance_start_date', 'insurance_expiry_date')
  def _check_insurance_dates(self):
    for rec in self:
      if (
          rec.insurance_start_date
          and rec.insurance_expiry_date
          and rec.insurance_expiry_date < rec.insurance_start_date
      ):
        raise ValidationError(
            _('تاريخ انتهاء التأمين لازم يكون بعد تاريخ البداية.')
        )

  @api.depends('state')
  def _compute_state_flags(self):
    for rec in self:
      rec.is_available = rec.state == 'available'
      rec.is_on_trip = rec.state == 'on_trip'
      rec.is_out_of_service = rec.state == 'out_of_service'

  def _inverse_is_available(self):
    for rec in self:
      if rec.is_available:
        rec.state = 'available'

  def _inverse_is_on_trip(self):
    for rec in self:
      if rec.is_on_trip:
        rec.state = 'on_trip'

  def _inverse_is_out_of_service(self):
    for rec in self:
      if rec.is_out_of_service:
        rec.state = 'out_of_service'

  @api.onchange('is_available')
  def _onchange_is_available(self):
    if self.is_available:
      self.state = 'available'
      self.is_on_trip = False
      self.is_out_of_service = False

  @api.onchange('is_on_trip')
  def _onchange_is_on_trip(self):
    if self.is_on_trip:
      self.state = 'on_trip'
      self.is_available = False
      self.is_out_of_service = False

  @api.onchange('is_out_of_service')
  def _onchange_is_out_of_service(self):
    if self.is_out_of_service:
      self.state = 'out_of_service'
      self.is_available = False
      self.is_on_trip = False

  @api.model
  def _expiry_status(self, expiry_date):
    """يرجع (الأيام المتبقية، الحالة) بناءً على تاريخ الانتهاء."""
    if not expiry_date:
      return 0, 'ok'
    today = fields.Date.context_today(self)
    days = (expiry_date - today).days
    if days < 0:
      return days, 'expired'
    if expiry_date <= today + relativedelta(months=1):
      return days, 'soon'
    return days, 'ok'

  @api.depends('license_expiry_date')
  def _compute_license_alert(self):
    for rec in self:
      rec.license_days_left, rec.license_alert_state = self._expiry_status(
          rec.license_expiry_date
      )

  @api.depends('insurance_expiry_date')
  def _compute_insurance_alert(self):
    for rec in self:
      rec.insurance_days_left, rec.insurance_alert_state = self._expiry_status(
          rec.insurance_expiry_date
      )

  @api.depends('maintenance_ids')
  def _compute_maintenance_count(self):
    for rec in self:
      rec.maintenance_count = len(rec.maintenance_ids)

  def _compute_handover_count(self):
    data = self.env['vehicle.handover']._read_group(
        [('vehicle_id', 'in', self.ids)], ['vehicle_id'], ['__count']
    )
    counts = {vehicle.id: count for vehicle, count in data}
    for rec in self:
      rec.handover_count = counts.get(rec.id, 0)

  def action_open_maintenance(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'name': _('الصيانة الشهرية - %s') % self.plate_number,
        'res_model': 'vehicle.maintenance',
        'view_mode': 'tree,form',
        'domain': [('vehicle_id', '=', self.id)],
        'context': {'default_vehicle_id': self.id},
    }

  def action_open_handover(self):
    self.ensure_one()
    if self.state != 'available':
      state_label = dict(self._fields['state'].selection).get(
          self.state, self.state
      )
      raise UserError(
          _('لا يمكن فتح صيانة قبل الاستلام لأن العربية غير متاحة.\n'
            'العربية: %(plate)s\n'
            'الحالة: %(state)s',
            plate=self.plate_number,
            state=state_label)
      )
    return {
        'type': 'ir.actions.act_window',
        'name': _('صيانة قبل الاستلام - %s') % self.plate_number,
        'res_model': 'vehicle.handover',
        'view_mode': 'tree,form',
        'domain': [('vehicle_id', '=', self.id)],
        'context': {'default_vehicle_id': self.id},
    }

  def write(self, vals):
    if 'license_expiry_date' in vals:
      vals['license_notified'] = False
    if 'insurance_expiry_date' in vals:
      vals['insurance_notified'] = False
    return super().write(vals)

  def _notify_expiry(self, kind):
    self.ensure_one()
    if kind == 'license':
      expiry, label = self.license_expiry_date, 'الرخصة'
    else:
      expiry, label = self.insurance_expiry_date, 'التأمين'
    user = (
        self.create_uid
        if self.create_uid.active
        else self.env.ref('base.user_admin')
    )
    summary = _(
        'تنبيه: %(label)s الخاصة بالعربية %(plate)s تنتهي بتاريخ %(date)s',
        label=label,
        plate=self.plate_number,
        date=expiry,
    )
    self.activity_schedule(
        'mail.mail_activity_data_todo',
        date_deadline=expiry,
        summary=summary,
        user_id=user.id,
    )
    self.message_post(body=summary, subtype_xmlid='mail.mt_note')
    self._send_expiry_email(label, expiry)

  def _get_alert_emails(self):
    self.ensure_one()
    partners = self.create_uid.partner_id | self.message_follower_ids.partner_id
    emails = {p.email.strip() for p in partners if p.email}
    if not emails:
      admin_email = self.env.ref('base.user_admin').partner_id.email
      if admin_email:
        emails.add(admin_email.strip())
    return sorted(emails)

  def _send_expiry_email(self, label, expiry):
    """يبعت إيميل تنبيه انتهاء الرخصة/التأمين. أي فشل في الإرسال لا يوقف الـ cron."""
    self.ensure_one()
    emails = self._get_alert_emails()
    if not emails:
      _logger.warning(
          'لا يوجد بريد إلكتروني لإرسال تنبيه %s للعربية %s', label, self.plate_number
      )
      return
    days_left = (expiry - fields.Date.context_today(self)).days
    if days_left < 0:
      status = 'انتهت بتاريخ %s' % expiry
    else:
      status = 'تنتهي بتاريخ %s (متبقي %s يوم)' % (expiry, days_left)
    subject = 'تنبيه: %s العربية %s تنتهي قريباً' % (label, self.plate_number)
    body = (
        '<div dir="rtl" style="font-family: Arial, sans-serif; font-size: 14px;">'
        '<p>السلام عليكم،</p>'
        '<p>نود تنبيهكم أن <b>%(label)s</b> الخاصة بالعربية رقم '
        '<b>%(plate)s</b> %(status)s.</p>'
        '<p>برجاء اتخاذ اللازم لتجديدها في أقرب وقت.</p>'
        '</div>'
    ) % {
        'label': html_escape(label),
        'plate': html_escape(self.plate_number),
        'status': html_escape(status),
    }
    email_from = (
        self.env.company.email_formatted
        or self.env.ref('base.user_admin').email_formatted
        or 'noreply@example.com'
    )
    try:
      self.env['mail.mail'].sudo().create({
          'subject': subject,
          'body_html': body,
          'email_from': email_from,
          'email_to': ','.join(emails),
          'model': self._name,
          'res_id': self.id,
          'auto_delete': True,
      }).send()
    except Exception:  # pylint: disable=broad-except
      _logger.exception('فشل إرسال إيميل تنبيه %s للعربية %s', label, self.plate_number)

  @api.model
  def _cron_check_expiry(self):
    limit = fields.Date.context_today(self) + relativedelta(months=1)

    licenses = self.search([
        ('license_expiry_date', '!=', False),
        ('license_expiry_date', '<=', limit),
        ('license_notified', '=', False),
    ])
    for rec in licenses:
      rec._notify_expiry('license')
    licenses.write({'license_notified': True})

    insurances = self.search([
        ('insurance_expiry_date', '!=', False),
        ('insurance_expiry_date', '<=', limit),
        ('insurance_notified', '=', False),
    ])
    for rec in insurances:
      rec._notify_expiry('insurance')
    insurances.write({'insurance_notified': True})