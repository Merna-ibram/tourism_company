import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

REMINDER_DAYS = 4


class VehicleMaintenance(models.Model):
  _name = 'vehicle.maintenance'
  _description = 'الصيانة الشهرية للعربية'
  _inherit = ['mail.thread', 'mail.activity.mixin']
  _order = 'maintenance_date desc, id desc'

  vehicle_id = fields.Many2one(
      'vehicle.vehicle',
      string='العربية',
      required=True,
      ondelete='cascade',
      index=True,
  )
  # True لما الشاشة تتفتح من زرار العربية، فتتقفل خانة العربية
  vehicle_locked = fields.Boolean(
      string='العربية مقفولة',
      store=False,
      default=lambda self: bool(self.env.context.get('default_vehicle_id')),
  )
  maintenance_date = fields.Date(
      string='تاريخ الصيانة',
      required=True,
      default=fields.Date.context_today,
      tracking=True,
  )
  problem = fields.Text(string='المشكلة', required=True)
  cost = fields.Monetary(string='التكلفة', currency_field='currency_id', required=True)
  currency_id = fields.Many2one(
      'res.currency',
      string='العملة',
      default=lambda self: self.env.company.currency_id,
  )
  spare_parts = fields.Text(string='قطع الغيار')
  maintenance_type = fields.Selection(
      [
          ('periodic', 'صيانة دورية'),
          ('repair', 'إصلاح'),
          ('oil', 'تغيير زيت'),
          ('tires', 'إطارات'),
          ('brakes', 'فرامل'),
          ('electric', 'كهرباء'),
          ('other', 'أخرى'),
      ],
      string='نوع الصيانة',
      default='periodic',
  )
  maintenance_center = fields.Char(string='مركز الصيانة', required=True)
  state = fields.Selection(
      [
          ('planned', 'مخططة (Planned)'),
          ('in_progress', 'جارية (In Progress)'),
          ('done', 'تمت (Done)'),
          ('cancelled', 'ملغاة (Cancelled)'),
      ],
      string='حالة الصيانة',
      default='planned',
      required=True,
      tracking=True,
  )
  is_planned = fields.Boolean(
      string='مخططة (Planned)',
      compute='_compute_state_flags',
      inverse='_inverse_is_planned',
  )
  is_in_progress = fields.Boolean(
      string='جارية (In Progress)',
      compute='_compute_state_flags',
      inverse='_inverse_is_in_progress',
  )
  is_done = fields.Boolean(
      string='تمت (Done)',
      compute='_compute_state_flags',
      inverse='_inverse_is_done',
  )
  is_cancelled = fields.Boolean(
      string='ملغاة (Cancelled)',
      compute='_compute_state_flags',
      inverse='_inverse_is_cancelled',
  )

  next_maintenance_date = fields.Date(
      string='تاريخ الصيانة القادمة', tracking=True, required=True
  )
  next_days_left = fields.Integer(
      string='الأيام المتبقية على الصيانة القادمة',
      compute='_compute_next_alert',
  )
  next_alert_state = fields.Selection(
      [
          ('none', 'غير محدد'),
          ('ok', 'ليس قريباً'),
          ('soon', 'قريبة'),
          ('overdue', 'متأخرة'),
      ],
      string='تنبيه الصيانة القادمة',
      compute='_compute_next_alert',
  )
  reminder_sent = fields.Boolean(
      string='تم إرسال التنبيه', default=False, copy=False
  )

  @api.depends('state')
  def _compute_state_flags(self):
    for rec in self:
      rec.is_planned = rec.state == 'planned'
      rec.is_in_progress = rec.state == 'in_progress'
      rec.is_done = rec.state == 'done'
      rec.is_cancelled = rec.state == 'cancelled'

  def _inverse_is_planned(self):
    for rec in self:
      if rec.is_planned:
        rec.state = 'planned'

  def _inverse_is_in_progress(self):
    for rec in self:
      if rec.is_in_progress:
        rec.state = 'in_progress'

  def _inverse_is_done(self):
    for rec in self:
      if rec.is_done:
        rec.state = 'done'

  def _inverse_is_cancelled(self):
    for rec in self:
      if rec.is_cancelled:
        rec.state = 'cancelled'

  @api.onchange('is_planned')
  def _onchange_is_planned(self):
    if self.is_planned:
      self.state = 'planned'
      self.is_in_progress = False
      self.is_done = False
      self.is_cancelled = False

  @api.onchange('is_in_progress')
  def _onchange_is_in_progress(self):
    if self.is_in_progress:
      self.state = 'in_progress'
      self.is_planned = False
      self.is_done = False
      self.is_cancelled = False

  @api.onchange('is_done')
  def _onchange_is_done(self):
    if self.is_done:
      self.state = 'done'
      self.is_planned = False
      self.is_in_progress = False
      self.is_cancelled = False

  @api.onchange('is_cancelled')
  def _onchange_is_cancelled(self):
    if self.is_cancelled:
      self.state = 'cancelled'
      self.is_planned = False
      self.is_in_progress = False
      self.is_done = False

  @api.depends('next_maintenance_date', 'state')
  def _compute_next_alert(self):
    today = fields.Date.context_today(self)
    for rec in self:
      if not rec.next_maintenance_date or rec.state == 'cancelled':
        rec.next_days_left = 0
        rec.next_alert_state = 'none'
        continue
      days = (rec.next_maintenance_date - today).days
      rec.next_days_left = days
      if days < 0:
        rec.next_alert_state = 'overdue'
      elif days <= REMINDER_DAYS:
        rec.next_alert_state = 'soon'
      else:
        rec.next_alert_state = 'ok'

  @api.constrains('cost')
  def _check_cost(self):
    for rec in self:
      if rec.cost <= 0:
        raise ValidationError(
            _('التكلفة لازم تكون أكبر من صفر.')
        )

  def write(self, vals):
    if 'vehicle_id' in vals:
      for rec in self:
        if rec.vehicle_id.id != vals['vehicle_id']:
          raise UserError(
              _('لا يمكن تغيير العربية بعد إنشاء سجل الصيانة.')
          )
    if 'next_maintenance_date' in vals:
      vals['reminder_sent'] = False
    return super().write(vals)

  def _notify_next_maintenance(self):
    self.ensure_one()
    expiry = self.next_maintenance_date
    user = (
        self.create_uid
        if self.create_uid.active
        else self.env.ref('base.user_admin')
    )
    summary = _(
        'تنبيه: الصيانة القادمة للعربية %(plate)s بتاريخ %(date)s',
        plate=self.vehicle_id.plate_number,
        date=expiry,
    )
    self.activity_schedule(
        'mail.mail_activity_data_todo',
        date_deadline=expiry,
        summary=summary,
        user_id=user.id,
    )
    self.message_post(body=summary, subtype_xmlid='mail.mt_note')
    self._send_maintenance_email(expiry)

  def _get_alert_emails(self):
    self.ensure_one()
    partners = self.create_uid.partner_id | self.message_follower_ids.partner_id
    emails = {p.email.strip() for p in partners if p.email}
    if not emails:
      admin_email = self.env.ref('base.user_admin').partner_id.email
      if admin_email:
        emails.add(admin_email.strip())
    return sorted(emails)

  def _send_maintenance_email(self, expiry):
    """يبعت إيميل تنبيه الصيانة القادمة. أي فشل في الإرسال لا يوقف الـ cron."""
    self.ensure_one()
    emails = self._get_alert_emails()
    plate = self.vehicle_id.plate_number or ''
    if not emails:
      _logger.warning(
          'لا يوجد بريد إلكتروني لإرسال تنبيه الصيانة للعربية %s', plate
      )
      return
    days_left = (expiry - fields.Date.context_today(self)).days
    status = 'بتاريخ %s (متبقي %s يوم)' % (expiry, days_left)
    subject = 'تنبيه: صيانة قادمة للعربية %s' % plate
    body = (
        '<div dir="rtl" style="font-family: Arial, sans-serif; font-size: 14px;">'
        '<p>السلام عليكم،</p>'
        '<p>نود تنبيهكم أن موعد <b>الصيانة القادمة</b> للعربية رقم '
        '<b>%(plate)s</b> %(status)s.</p>'
        '<p>برجاء اتخاذ اللازم لتجهيز العربية للصيانة.</p>'
        '</div>'
    ) % {
        'plate': html_escape(plate),
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
      _logger.exception('فشل إرسال إيميل تنبيه الصيانة للعربية %s', plate)

  @api.model
  def _cron_next_maintenance_reminder(self):
    today = fields.Date.context_today(self)
    limit = today + timedelta(days=REMINDER_DAYS)
    records = self.search([
        ('next_maintenance_date', '>=', today),
        ('next_maintenance_date', '<=', limit),
        ('reminder_sent', '=', False),
        ('state', '!=', 'cancelled'),
    ])
    for rec in records:
      rec._notify_next_maintenance()
    records.write({'reminder_sent': True})