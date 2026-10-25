
# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DriverProfile(models.Model):
    _name = "driver.profile"
    _description = "ملف السائق"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "name"

    # بيانات السائق
    name = fields.Char(
        string="اسم السائق",
        required=True,
        tracking=True,
    )

    image_1920 = fields.Image(string="صورة السائق")

    mobile = fields.Char(
        string="رقم الموبايل",
        required=True,
        tracking=True,
        size=11,
        copy=False,
    )

    national_id = fields.Char(
        string="الرقم القومي",
        required=True,
        tracking=True,
        copy=False,
        size=14,
    )

    hire_date = fields.Date(
        string="تاريخ التعيين",
        required=True,
        default=fields.Date.context_today,
    )

    # بيانات رخصة القيادة
    license_number = fields.Char(
        string="رقم الرخصة",
        required=True,
        tracking=True,
        copy=False,
    )

    license_type = fields.Selection(
        [
            ("private", "خاصة"),
            ("professional_3", "مهنية درجة ثالثة"),
            ("professional_2", "مهنية درجة ثانية"),
            ("professional_1", "مهنية درجة أولى"),
            ("motorcycle", "دراجة نارية"),
            ("other", "أخرى"),
        ],
        string="نوع الرخصة",
        required=True,
        default="private",
    )

    license_expiry_date = fields.Date(
        string="تاريخ انتهاء الرخصة",
        required=True,
        tracking=True,
    )

    license_days_left = fields.Integer(
        string="الأيام المتبقية على انتهاء الرخصة",
        compute="_compute_license_alert",
    )

    license_alert_state = fields.Selection(
        [
            ("ok", "سارية"),
            ("soon", "تنتهي خلال شهر"),
            ("expired", "منتهية"),
        ],
        string="حالة الرخصة",
        compute="_compute_license_alert",
    )

    license_notified = fields.Boolean(
        string="تم إرسال تنبيه الرخصة",
        default=False,
        copy=False,
    )

    # ربط السائق بالعربية
    vehicle_id = fields.Many2one(
        "vehicle.vehicle",
        string="العربية المرتبطة",
        tracking=True,
        ondelete="set null",
        help="اختاري العربية المرتبطة بالسائق من السيارات المسجلة.",
    )

    # الحالة الأساسية للسائق
    state = fields.Selection(
        [
            ("available", "متاح"),
            ("on_trip", "في رحلة"),
            ("off", "خارج الخدمة"),
            ("suspended", "موقوف"),
        ],
        string="حالة السائق",
        required=True,
        default="available",
        tracking=True,
    )

    # مربعات الحالة
    is_available = fields.Boolean(
        string="متاح",
        compute="_compute_state_flags",
        inverse="_inverse_is_available",
    )

    is_on_trip = fields.Boolean(
        string="في رحلة",
        compute="_compute_state_flags",
        inverse="_inverse_is_on_trip",
    )

    is_off = fields.Boolean(
        string="خارج الخدمة",
        compute="_compute_state_flags",
        inverse="_inverse_is_off",
    )

    is_suspended = fields.Boolean(
        string="موقوف",
        compute="_compute_state_flags",
        inverse="_inverse_is_suspended",
    )

    _sql_constraints = [
        (
            "driver_national_id_uniq",
            "unique(national_id)",
            "الرقم القومي مسجل لسائق آخر.",
        ),
        (
            "driver_license_number_uniq",
            "unique(license_number)",
            "رقم الرخصة مسجل لسائق آخر.",
        ),
    ]

    # التحقق من الرقم القومي
    @api.constrains("national_id")
    def _check_national_id(self):
        for rec in self:
            if rec.national_id and (
                not rec.national_id.isdigit()
                or len(rec.national_id) != 14
            ):
                raise ValidationError(
                    _("الرقم القومي يجب أن يتكون من 14 رقمًا بالضبط.")
                )

    # التحقق من رقم الموبايل
    @api.constrains("mobile")
    def _check_mobile(self):
        for rec in self:
            if rec.mobile and (
                not rec.mobile.isdigit()
                or len(rec.mobile) != 11
            ):
                raise ValidationError(
                    _("رقم الموبايل يجب أن يتكون من 11 رقمًا بالضبط.")
                )

    # التحقق من تاريخ التعيين
    @api.constrains("hire_date")
    def _check_hire_date(self):
        today = fields.Date.context_today(self)

        for rec in self:
            if rec.hire_date and rec.hire_date > today:
                raise ValidationError(
                    _("تاريخ التعيين لا يمكن أن يكون في المستقبل.")
                )

    # حساب الأيام المتبقية وحالة الرخصة
    @api.depends("license_expiry_date")
    def _compute_license_alert(self):
        today = fields.Date.context_today(self)
        limit = today + relativedelta(months=1)

        for rec in self:
            if not rec.license_expiry_date:
                rec.license_days_left = 0
                rec.license_alert_state = "ok"
                continue

            days = (rec.license_expiry_date - today).days
            rec.license_days_left = days

            if days < 0:
                rec.license_alert_state = "expired"
            elif rec.license_expiry_date <= limit:
                rec.license_alert_state = "soon"
            else:
                rec.license_alert_state = "ok"

    # مزامنة مربعات الحالة مع الحالة الأساسية
    @api.depends("state")
    def _compute_state_flags(self):
        for rec in self:
            rec.is_available = rec.state == "available"
            rec.is_on_trip = rec.state == "on_trip"
            rec.is_off = rec.state == "off"
            rec.is_suspended = rec.state == "suspended"

    # تحديث الحالة عند اختيار مربع الحالة
    def _inverse_is_available(self):
        for rec in self:
            if rec.is_available:
                rec.state = "available"

    def _inverse_is_on_trip(self):
        for rec in self:
            if rec.is_on_trip:
                rec.state = "on_trip"

    def _inverse_is_off(self):
        for rec in self:
            if rec.is_off:
                rec.state = "off"

    def _inverse_is_suspended(self):
        for rec in self:
            if rec.is_suspended:
                rec.state = "suspended"

    # إنشاء سجل السائق ومزامنة اسم السائق مع العربية
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_vehicle_driver_name()
        return records

    # تحديث بيانات السائق
    def write(self, vals):
        old_vehicles = self.mapped("vehicle_id")
        result = super().write(vals)

        if "license_expiry_date" in vals:
            self.write({"license_notified": False})

        if "vehicle_id" in vals or "name" in vals:
            (
                old_vehicles | self.mapped("vehicle_id")
            )._sync_driver_name_from_profile()

        return result

    # مزامنة اسم السائق مع العربية المرتبطة
    def _sync_vehicle_driver_name(self):
        for rec in self:
            if rec.vehicle_id:
                rec.vehicle_id.sudo().write({
                    "driver_name": rec.name,
                })

    # تنبيه انتهاء الرخصة
    def _cron_check_license_expiry(self):
        today = fields.Date.context_today(self)
        limit = today + relativedelta(months=1)

        drivers = self.search([
            ("license_expiry_date", "!=", False),
            ("license_expiry_date", "<=", limit),
            ("license_notified", "=", False),
        ])

        for driver in drivers:
            user = (
                driver.create_uid
                if driver.create_uid and driver.create_uid.active
                else self.env.ref("base.user_admin")
            )

            driver.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=today,
                summary=_(
                    "تنبيه: رخصة السائق %s تنتهي بتاريخ %s"
                ) % (
                    driver.name,
                    driver.license_expiry_date,
                ),
                user_id=user.id,
            )

            driver.message_post(
                body=_(
                    "تنبيه: رخصة السائق %s تنتهي بتاريخ %s."
                ) % (
                    driver.name,
                    driver.license_expiry_date,
                ),
                subtype_xmlid="mail.mt_note",
            )

        drivers.write({"license_notified": True})


class VehicleVehicle(models.Model):
    _inherit = "vehicle.vehicle"

    def _sync_driver_name_from_profile(self):
        for vehicle in self:
            driver = self.env["driver.profile"].search(
                [("vehicle_id", "=", vehicle.id)],
                limit=1,
            )

            driver_name = driver.name if driver else False

            if vehicle.driver_name != driver_name:
                vehicle.sudo().write({
                    "driver_name": driver_name,
                })
