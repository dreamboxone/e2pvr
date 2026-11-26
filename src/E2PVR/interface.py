# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
import os
import sys
import textwrap
from xml.sax.saxutils import escape
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import (config, configfile, ConfigSubsection,
    ConfigSelection, ConfigSlider, ConfigYesNo, KEY_LEFT, KEY_RIGHT)
from Screens.Screen import Screen
from enigma import ePoint, eTimer, getDesktop
try:
    from enigma import addFont
except ImportError:
    addFont = None
from .core import SubtitleTrack, overlay_geometry, logger, steady_time, split_cues, CueScheduler
from .service import KEY_FILE, DEFAULT_MODEL, MODELS, read_key, ServiceError
from .runtime import Runtime
from . import VERSION, PACKAGE_DIR
from .raster import Rasterizer
try:
    from Components.Pixmap import Pixmap
    from Tools.LoadPixmap import LoadPixmap
    from enigma import eSize
except ImportError:
    Pixmap = LoadPixmap = None


def native_text(text):
    if sys.version_info[0] == 2 and isinstance(text, unicode):
        return text.encode("utf-8")
    return text


COLORS = [("ffffff", "White"), ("ffff00", "Yellow"), ("00ff00", "Green"), ("00ffff", "Cyan")]
SIZES = [("small", "Small"), ("medium", "Medium"), ("large", "Large")]


def available_fonts():
    choices = [("Regular", "Regular")]
    if addFont is None:
        return choices
    bundled = os.path.join(PACKAGE_DIR, "Vazirmatn-SemiBold.ttf")
    if os.path.isfile(bundled):
        try:
            addFont(native_text(bundled), "E2PVR_Vazirmatn", 100, False)
            choices.insert(0, ("E2PVR_Vazirmatn", "Vazirmatn"))
        except Exception:
            logger().exception("Unable to register subtitle font")
    directory = "/usr/share/fonts"
    if os.path.isdir(directory):
        for filename in sorted(os.listdir(directory)):
            if filename.lower().endswith((".ttf", ".otf")):
                alias = "E2PVR_" + os.path.splitext(filename)[0]
                try:
                    addFont(native_text(os.path.join(directory, filename)), native_text(alias), 100, False)
                    choices.append((alias, os.path.splitext(filename)[0]))
                except Exception:
                    logger().exception("Unable to register system font")
    return choices


if not hasattr(config.plugins, "e2pvr"):
    config.plugins.e2pvr = ConfigSubsection()
settings = config.plugins.e2pvr
if not hasattr(settings, "language"):
    settings.language = ConfigSelection(default="en", choices=[("en", "English"), ("fa", "فارسی"), ("ar", "العربية")])
    settings.enabled = ConfigYesNo(default=False)
    settings.target = ConfigSelection(default="fa", choices=[("fa", "فارسی"), ("ar", "العربية"), ("ru", "Русский")])
    settings.color = ConfigSelection(default="ffff00", choices=COLORS)
    settings.size = ConfigSelection(default="small", choices=SIZES)
    fonts = available_fonts()
    settings.font = ConfigSelection(default=fonts[0][0], choices=fonts)
    settings.position = ConfigSlider(default=100, increment=1, limits=(0, 100))
    settings.transparency = ConfigSlider(default=65, increment=5, limits=(0, 100))
if not hasattr(settings, "model"):
    settings.model = ConfigSelection(default=DEFAULT_MODEL, choices=[(model, model) for model in MODELS])
if not hasattr(settings, "sync"):
    settings.sync = ConfigSelection(default="0.00", choices=[("%.2f" % (step / 4.0), "%.2f" % (step / 4.0)) for step in range(-16, 15)])
if not hasattr(settings, "startup_delay"):
    settings.startup_delay = ConfigSelection(default="4", choices=[(str(seconds), str(seconds)) for seconds in range(5)])


TRANSLATIONS = {
    "Settings": ("تنظیمات", "الإعدادات"), "Enabled": ("فعال", "تفعيل"),
    "Interface language": ("زبان برنامه", "لغة الواجهة"), "Subtitle language": ("زبان زیرنویس", "لغة الترجمة"),
    "Color": ("رنگ", "اللون"), "Font": ("فونت", "الخط"), "Font size": ("اندازه فونت", "حجم الخط"),
    "Vertical position (%)": ("موقعیت عمودی (درصد)", "الموضع الرأسي (%)"),
    "Box transparency (%)": ("شفافیت کادر (درصد)", "شفافية الإطار (%)"),
    "Subtitle timing (seconds)": ("تنظیم زمان زیرنویس (ثانیه)", "توقيت الترجمة (ثانية)"),
    "Startup delay (seconds)": ("تأخیر آغاز پخش (ثانیه)", "تأخير بدء التشغيل (ثانية)"),
    "Service model": ("مدل سرویس", "نموذج الخدمة"), "Save": ("ذخیره", "حفظ"),
    "Cancel": ("انصراف", "إلغاء"), "Check connection": ("آزمایش اتصال", "اختبار الاتصال"),
    "White": ("سفید", "أبيض"), "Yellow": ("زرد", "أصفر"), "Green": ("سبز", "أخضر"),
    "Cyan": ("فیروزه‌ای", "سماوي"), "Small": ("کوچک", "صغير"),
    "Medium": ("متوسط", "متوسط"), "Large": ("بزرگ", "كبير"),
    "Yes": ("بله", "نعم"), "No": ("خیر", "لا"),
    "Key file is missing: /root/apikey.txt": ("فایل کلید موجود نیست: /root/apikey.txt", "ملف المفتاح غير موجود: /root/apikey.txt"),
    "Invalid key file: /root/apikey.txt": ("فایل کلید نامعتبر است: /root/apikey.txt", "ملف المفتاح غير صالح: /root/apikey.txt"),
    "Key file is empty: /root/apikey.txt": ("فایل کلید خالی است: /root/apikey.txt", "ملف المفتاح فارغ: /root/apikey.txt"),
    "Key file found. Internet is required.": ("فایل کلید موجود است. اتصال اینترنت لازم است.", "ملف المفتاح موجود. يلزم اتصال بالإنترنت."),
    "Checking connection...": ("در حال آزمایش اتصال...", "جار اختبار الاتصال..."),
    "Connection successful": ("اتصال موفق بود", "نجح الاتصال"),
    "Start translation": ("شروع ترجمه", "بدء الترجمة"),
    "Stop translation": ("توقف ترجمه", "إيقاف الترجمة"),
    "Translation stopped": ("ترجمه متوقف است", "الترجمة متوقفة"),
    "Ready - play a recorded movie": ("آماده؛ یک فیلم ضبط‌شده پخش کنید", "جاهز؛ شغل فيلما مسجلا"),
    "Press Start to select a recorded movie": ("برای انتخاب فیلم ضبط‌شده، شروع را بزنید", "اضغط بدء لاختيار فيلم مسجل"),
    "Connecting to subtitle service...": ("در حال اتصال به سرویس زیرنویس...", "جار الاتصال بخدمة الترجمة..."),
    "Translating recording": ("در حال ترجمه فیلم", "جار ترجمة التسجيل"),
    "Connection test timed out; check receiver network": ("مهلت آزمایش تمام شد؛ شبکه ریسیور را بررسی کنید", "انتهت مهلة الاختبار؛ تحقق من شبكة الجهاز"),
    "DNS lookup failed; check receiver network": ("نام سرویس پیدا نشد؛ شبکه ریسیور را بررسی کنید", "تعذر العثور على الخدمة؛ تحقق من شبكة الجهاز"),
    "Live setup timed out": ("مهلت آماده‌سازی اتصال تمام شد", "انتهت مهلة إعداد الاتصال"),
    "API key rejected": ("کلید سرویس پذیرفته نشد", "تم رفض مفتاح الخدمة"),
    "Service access denied": ("دسترسی به سرویس مجاز نیست", "تم رفض الوصول إلى الخدمة"),
    "Service model unavailable": ("مدل سرویس در دسترس نیست", "نموذج الخدمة غير متاح"),
    "Service quota exceeded": ("سهمیه سرویس تمام شده است", "تم تجاوز حصة الخدمة"),
    "Secure connection failed or timed out": ("اتصال امن برقرار نشد یا زمان آن تمام شد", "فشل الاتصال الآمن أو انتهت مهلته"),
    "Network route denied by service": ("مسیر اتصال به سرویس مسدود شده است", "مسار الاتصال بالخدمة محظور"),
    "Live connection failed; retrying": ("اتصال برقرار نشد؛ تلاش مجدد", "فشل الاتصال؛ جار إعادة المحاولة"),
    "Live connection interrupted; reconnecting": ("اتصال قطع شد؛ اتصال مجدد", "انقطع الاتصال؛ جار إعادة الاتصال"),
    "Live service unavailable": ("سرویس در دسترس نیست", "الخدمة غير متاحة"),
    "Invalid service request": ("درخواست سرویس نامعتبر است", "طلب الخدمة غير صالح"),
    "Unable to decode recording audio": ("خواندن صدای فایل ضبط‌شده ممکن نیست", "تعذر قراءة صوت التسجيل"),
    "Subtitle processing failed": ("پردازش زیرنویس متوقف شد", "توقفت معالجة الترجمة"),
    "Processing worker stopped": ("پردازش متوقف شده است", "توقفت المعالجة"),
}


def tr(text):
    language = settings.language.value
    values = TRANSLATIONS.get(native_text(text).replace("/home/root/apikey.txt", "/root/apikey.txt"))
    value = values[0 if language == "fa" else 1] if values and language != "en" else native_text(text)
    return value.replace("/root/apikey.txt", KEY_FILE)


def bind_timer(timer, callback):
    if hasattr(timer, "callback"):
        timer.callback.append(callback)
        return None
    return timer.timeout.connect(callback)


class SettingsScreen(Screen):
    def __init__(self, session):
        desktop = getDesktop(0).size()
        width, height = min(1100, desktop.width() - 40), min(700, desktop.height() - 40)
        row_height = (height - 160) // 9
        point_size = min(28, max(18, row_height - 12))
        button_width = (width - 40) // 4
        columns = []
        for index in range(9):
            columns.append('<widget name="row%d_label" position="20,%d" size="%d,%d" font="Regular;%d" halign="left" valign="center" />' %
                           (index, 20 + index * row_height, width * 3 // 5 - 35, row_height, point_size))
            columns.append('<widget name="row%d_value" position="%d,%d" size="%d,%d" font="Regular;%d" halign="right" valign="center" />' %
                           (index, width * 3 // 5, 20 + index * row_height, width * 2 // 5 - 20, row_height, point_size))
        self.skin = '''<screen name="E2PVRSettings" position="center,center" size="%d,%d" title="E2PVR">
            %s
            <widget name="status" position="20,%d" size="%d,70" font="Regular;22" />
            <widget name="publisher" position="20,%d" size="%d,30" font="Regular;20" halign="center" />
            <widget name="start" position="20,%d" size="%d,35" font="Regular;22" foregroundColor="#ff5555" />
            <widget name="save" position="%d,%d" size="%d,35" font="Regular;22" foregroundColor="#00ff00" />
            <widget name="test" position="%d,%d" size="%d,35" font="Regular;22" foregroundColor="#ffff00" />
            <widget name="stop" position="%d,%d" size="%d,35" font="Regular;22" foregroundColor="#5599ff" />
        </screen>''' % (width, height, "".join(columns), height - 140, width - 40, height - 78, width - 40,
            height - 45, button_width, 20 + button_width, height - 45, button_width,
            20 + 2 * button_width, height - 45, button_width, 20 + 3 * button_width, height - 45, button_width)
        Screen.__init__(self, session)
        self.selection = 0
        for index in range(9):
            self["row%d_label" % index], self["row%d_value" % index] = Label(""), Label("")
        self.rtl_columns = False
        self.onLayoutFinish.append(self.layout_rows)
        for name in ("start", "save", "test", "stop"):
            self[name] = Label("")
        self["status"] = Label("")
        self["publisher"] = Label("Copyright 2026 Routekernel | t.me/routekernel1")
        self.selecting_recording = False
        self.test_result = None
        self.timer = eTimer()
        self.connection = bind_timer(self.timer, self.update_test)
        self.onClose.append(self.timer.stop)
        self.onClose.append(monitor.cancel_connection_test)
        # DreamOS also maps red to cancel in SetupActions.
        self["actions"] = ActionMap(["ColorActions", "OkCancelActions", "DirectionActions"], {
            "green": self.save, "red": self.start_translation, "blue": self.stop_translation, "cancel": self.cancel,
            "yellow": self.check_connection, "left": self.keyLeft, "right": self.keyRight,
            "leftRepeated": self.keyLeft, "rightRepeated": self.keyRight,
            "up": lambda: self.move(-1), "down": lambda: self.move(1)}, -2)
        self.rebuild()
        self.timer.start(200)

    def start_translation(self):
        if settings.enabled.value or self.selecting_recording:
            return
        self.test_result = None
        try:
            read_key()
        except ServiceError as error:
            logger().warning("Translation not started: %s", error)
            self["status"].setText(tr(str(error)))
            return
        ref = self.session.nav.getCurrentlyPlayingServiceReference()
        if not ref or not ref.getPath() or not os.path.isfile(ref.getPath()):
            from Screens.MovieSelection import MovieSelection
            self.selecting_recording = True
            self.session.openWithCallback(self.recording_selected, MovieSelection)
            return
        monitor.start_translation()
        settings.enabled.save()
        monitor.poll()
        self.save()

    def stop_translation(self):
        if not settings.enabled.value:
            return
        self.test_result = None
        monitor.stop_translation("remote control")
        configfile.save()
        self.rebuild()

    def recording_selected(self, reference):
        self.selecting_recording = False
        if reference is None:
            return
        if not reference.getPath() or not os.path.isfile(reference.getPath()):
            self["status"].setText(tr("Ready - play a recorded movie"))
            return
        monitor.start_translation()
        settings.enabled.save()
        for unused, setting in self.rows:
            setting.save()
        configfile.save()
        self.close(reference)

    def refresh_status(self):
        if (monitor and monitor.connection_test) or self.test_result is not None:
            return
        try:
            read_key()
            state = monitor.runtime.state() if monitor and monitor.runtime else {}
            if not settings.enabled.value:
                ref = self.session.nav.getCurrentlyPlayingServiceReference()
                status = "Translation stopped" if ref and ref.getPath() else "Press Start to select a recorded movie"
            elif state.get("error"):
                status = state["error"]
            elif not monitor or not monitor.path:
                status = "Ready - play a recorded movie"
            elif state.get("ready"):
                status = "Translating recording"
            else:
                status = "Connecting to subtitle service..."
        except ServiceError as error:
            status = str(error)
        self["status"].setText(tr(status))

    def rebuild(self):
        self.setTitle("E2PVR " + VERSION + " - " + tr("Settings"))
        self.rows = [("Interface language", settings.language),
            ("Subtitle language", settings.target), ("Color", settings.color), ("Font", settings.font),
            ("Font size", settings.size), ("Vertical position (%)", settings.position),
            ("Box transparency (%)", settings.transparency), ("Subtitle timing (seconds)", settings.sync),
            ("Startup delay (seconds)", settings.startup_delay)]
        for name, label in [("start", "Start translation"), ("save", "Save"),
                            ("test", "Check connection"), ("stop", "Stop translation")]:
            self[name].setText(tr(label))
        try:
            read_key()
            status = "Key file found. Internet is required."
            if monitor and monitor.runtime and monitor.runtime.state().get("error"):
                status = monitor.runtime.state()["error"]
        except ServiceError as error:
            status = str(error)
        self["status"].setText(tr(status))
        self.refresh_status()
        self.refresh_rows()

    def move(self, direction):
        self.selection = (self.selection + direction) % len(self.rows)
        self.refresh_rows()

    def layout_rows(self):
        self.rtl_columns = False  # The skin applies the original column positions.
        self.refresh_rows()

    def refresh_rows(self):
        if not hasattr(self, "rows"):
            return
        from enigma import gRGB
        rtl = settings.language.value in ("fa", "ar")
        mirror = self.instance is not None and rtl != self.rtl_columns
        if mirror:
            width = self.instance.child().size().width()
        selected = self.selection
        for index, (label, setting) in enumerate(self.rows):
            self["row%d_label" % index].setText(tr(label))
            if setting is settings.enabled:
                text = tr("Yes" if setting.value else "No")
            elif setting in (settings.position, settings.transparency):
                text = "%d%%" % setting.value
            elif setting in (settings.color, settings.size):
                text = tr(setting.getText())
            else:
                text = native_text(setting.getText())
            self["row%d_value" % index].setText(text)
            for column in ("label", "value"):
                instance = self["row%d_%s" % (index, column)].instance
                if instance:
                    if mirror:
                        position = instance.position()
                        instance.move(ePoint(width - position.x() - instance.size().width(), position.y()))
                        align_right = rtl or column == "value"
                        instance.setHAlign(instance.alignRight if align_right else instance.alignLeft)
                    instance.setForegroundColor(gRGB(0x00ffff00 if index == selected else 0x00ffffff))
        if mirror:
            self.rtl_columns = rtl

    def keyLeft(self):
        self.rows[self.selection][1].handleKey(KEY_LEFT)
        self.rebuild()

    def keyRight(self):
        self.rows[self.selection][1].handleKey(KEY_RIGHT)
        self.rebuild()

    def check_connection(self):
        if monitor.connection_test:
            return
        self.test_started = steady_time()
        self.test_result = None
        self["status"].setText(tr("Checking connection..."))
        try:
            monitor.connection_test = Runtime(settings.target.value)
        except Exception:
            logger().exception("Unable to start connection test")
            self.finish_connection_test("Processing worker stopped")

    def finish_connection_test(self, result):
        monitor.cancel_connection_test()
        logger().info("Connection test: %s", result)
        self.test_result = result
        self.test_finished = steady_time()
        self["status"].setText(tr(result))

    def update_test(self):
        if monitor and monitor.connection_test:
            state = monitor.connection_test.state()
            if state.get("ready"):
                self.finish_connection_test("Connection successful")
            elif state.get("error"):
                self.finish_connection_test(state["error"])
            elif steady_time() - self.test_started >= 60:
                self.finish_connection_test("Connection test timed out; check receiver network")
        elif self.test_result is not None and steady_time() - self.test_finished >= 5:
            self.test_result = None
        self.refresh_status()

    def save(self):
        for _, value in self.rows:
            value.save()
        configfile.save()
        self.close()

    def cancel(self):
        for _, value in self.rows:
            value.cancel()
        self.close()


class Overlay(Screen):
    def __init__(self, session):
        width, height = getDesktop(0).size().width(), getDesktop(0).size().height()
        x, y, box_width, box_height, points = overlay_geometry(width, height, settings.position.value, settings.size.value)
        self.line_chars = max(24, min(96, int(46 * 64.0 / points * width / 1920.0)))
        alpha = int(255 * settings.transparency.value / 100.0)
        self.skin = '''<screen name="E2PVROverlay" position="%d,%d" size="%d,%d" zPosition="10" flags="wfNoBorder" backgroundColor="#%02x000000">
            <widget name="bitmap" position="0,0" size="%d,%d" transparent="1" alphatest="blend" />
            <widget name="text" position="10,8" size="%d,%d" font="%s;%d" halign="center" valign="center" transparent="1" noWrap="1" foregroundColor="#%s" />
            <widget name="line2" position="10,%d" size="%d,%d" font="%s;%d" halign="center" valign="center" transparent="1" noWrap="1" foregroundColor="#%s" />
        </screen>''' % (x, y, box_width, box_height, alpha, box_width, box_height, box_width - 20, box_height // 2 - 8,
                        escape(settings.font.value), points, settings.color.value,
                        box_height // 2, box_width - 20, box_height // 2 - 8,
                        escape(settings.font.value), points, settings.color.value)
        Screen.__init__(self, session)
        self["text"] = Label("")
        self["line2"] = Label("")
        self["bitmap"] = Pixmap() if Pixmap else Label("")
        self["bitmap"].hide()
        self.last_text = None
        self.raster = None
        self.raster_visible = False
        self.box_width, self.box_height = box_width, box_height
        if Pixmap and LoadPixmap and os.access("/usr/bin/pango-view", os.X_OK):
            try:
                font_path = None
                if settings.font.value == "E2PVR_Vazirmatn":
                    font_path = os.path.join(PACKAGE_DIR, "Vazirmatn-SemiBold.ttf")
                elif settings.font.value.startswith("E2PVR_"):
                    for name in os.listdir("/usr/share/fonts"):
                        if os.path.splitext(name)[0] == settings.font.value[6:]:
                            font_path = os.path.join("/usr/share/fonts", name)
                            break
                self.raster = Rasterizer(font_path, points, box_width - 4, settings.color.value)
                self.onClose.append(self.raster.close)
            except Exception:
                logger().exception("Subtitle shaping unavailable")

    def display(self, text):
        if text != self.last_text:
            self.last_text = text
            self.raster_visible = False
            self["bitmap"].hide()
            self["text"].show()
            self["line2"].show()
            if self.raster:
                try:
                    self.raster.request(text)
                except Exception:
                    logger().exception("Subtitle shaping failed")
        job = self.raster.poll() if self.raster else None
        if job:
            try:
                import struct
                path = job["stem"] + ".png"
                with open(path, "rb") as stream:
                    header = stream.read(24)
                width, height = struct.unpack(">II", header[16:24])
                pixmap = LoadPixmap(native_text(path), desktop=getDesktop(0), cached=False)
                if pixmap is None:
                    raise ValueError("Subtitle image unavailable")
                self["bitmap"].setPixmap(pixmap)
                self["bitmap"].instance.resize(eSize(width, height))
                self["bitmap"].instance.move(ePoint(max(0, (self.box_width - width) // 2), max(0, (self.box_height - height) // 2)))
                self["bitmap"].show()
                self.raster_visible = True
                self["text"].hide()
                self["line2"].hide()
            except Exception:
                logger().exception("Subtitle image display failed")
            finally:
                self.raster.discard(job)
        if text:
            lines = text.split("\n")
            self["text"].setText(native_text(lines[0]))
            self["line2"].setText(native_text(lines[1] if len(lines) > 1 else ""))
            self.show()
        else:
            self["text"].setText("")
            self["line2"].setText("")
            self.hide()


class PlaybackMonitor(object):
    def __init__(self, session):
        self.session = session
        self.timer = eTimer()
        self.connection = bind_timer(self.timer, self.poll)
        self.path = None
        self.style = None
        self.track = None
        self.overlay = None
        self.runtime = None
        self.connection_test = None
        self.generation = 0
        self.key_stamp = None
        self.previous_position = None
        self.previous_time = None
        self.preparing = None
        self.preview_position = None
        self.rewind_guard_until = 0
        self.paused = None
        self.last_error = None
        self.scheduler = CueScheduler()
        self.correction = None
        self.audio_stream = None
        self.standby_counter = getattr(config.misc, "standbyCounter", None)
        if self.standby_counter is not None:
            self.standby_counter.addNotifier(self.enter_standby, initial_call=False)

    def start_translation(self):
        settings.enabled.value = True
        self.timer.start(100)
        logger().info("Translation requested: target=%s", settings.target.value)

    def cancel_connection_test(self):
        test, self.connection_test = self.connection_test, None
        if test is not None:
            test.stop()

    def enter_standby(self, unused):
        self.cancel_connection_test()
        self.stop_translation("standby")

    def release(self):
        if self.paused is not None:
            try:
                self.paused.unpause()
            except Exception:
                logger().exception("Unable to resume playback")
        self.paused = self.preparing = None

    def clear(self):
        self.release()
        if self.overlay:
            self.session.deleteDialog(self.overlay)
        self.overlay = None
        self.track = None
        self.previous_position = self.previous_time = None
        self.scheduler.reset()
        self.audio_stream = None
        self.preview_position = None
        self.rewind_guard_until = 0

    def poll(self):
        try:
            self.update()
        except Exception:
            logger().exception("Playback monitor failed")
            self.stop_translation("playback monitor error")

    def update(self):
        if not settings.enabled.value:
            self.clear()
            self.path = None
            if self.runtime:
                self.runtime.stop()
                self.runtime = None
            return
        stamp = (os.path.getmtime(KEY_FILE), os.path.getsize(KEY_FILE)) if os.path.isfile(KEY_FILE) else None
        if self.runtime is None or stamp != self.key_stamp:
            if self.runtime:
                self.runtime.stop()
            self.key_stamp = stamp
            self.runtime = Runtime(settings.target.value)
        ref = self.session.nav.getCurrentlyPlayingServiceReference()
        path = ref.getPath() if ref else ""
        if not path or not os.path.isfile(path):
            if self.path:
                self.generation += 1
                self.runtime.command("", settings.target.value, settings.model.value, self.generation, 0)
            self.clear()
            self.path = None
            return
        style = tuple(value.value for value in (settings.target, settings.color, settings.size,
            settings.font, settings.position, settings.transparency, settings.model))
        changed_path = path != self.path
        if changed_path or style != self.style:
            stream_changed = changed_path or self.style is None or self.style[0] != style[0] or self.style[-1] != style[-1]
            previous_audio = self.audio_stream
            self.clear()
            self.path, self.style = path, style
            if stream_changed:
                self.generation += 1
            else:
                self.audio_stream = previous_audio
            candidates = [os.path.splitext(path)[0] + "." + settings.target.value + ".srt", path + "." + settings.target.value + ".srt"]
            for candidate in candidates:
                if os.path.isfile(candidate):
                    self.track = SubtitleTrack.load(candidate)
                    break
            self.overlay = self.session.instantiateDialog(Overlay)
            if self.track:
                formatted = split_cues([dict(start=start, end=end, text=text) for start, end, text in self.track.cues], self.overlay.line_chars)
                self.track = SubtitleTrack([(cue["start"], cue["end"], cue["text"]) for cue in formatted])
            if changed_path and not self.track and stamp is not None and int(settings.startup_delay.value) > 0:
                self.preparing = steady_time()
        service = self.session.nav.getCurrentService()
        seek = service.seek() if service else None
        position_result = seek.getPlayPosition() if seek else (1, 0)
        if position_result[0]:
            if self.preparing is not None and steady_time() - self.preparing >= int(settings.startup_delay.value):
                self.release()
            self.overlay.hide()
            return
        position = max(0, position_result[1] // 90)
        now = steady_time()
        state = self.runtime.state()
        if self.preparing is not None:
            if self.preview_position is None:
                self.preview_position = position
            if state.get("error"):
                self.release()
            elif position - self.preview_position >= int(settings.startup_delay.value) * 1000:
                origin = self.preview_position
                if seek.seekTo(origin * 90) == 0:
                    position = origin
                    self.previous_position = self.previous_time = None
                    self.rewind_guard_until = now + 1
                    logger().info("Initial preview rewound: origin_ms=%d preview_ms=%d", origin, int(settings.startup_delay.value) * 1000)
                else:
                    logger().warning("Unable to rewind initial preview")
                self.release()
        if self.previous_position is not None and self.preparing is None and now >= self.rewind_guard_until:
            delta = position - self.previous_position
            if delta < -1000 or delta > (now - self.previous_time) * 1000 + 1500:
                self.generation += 1
                self.scheduler.reset()
        self.previous_position, self.previous_time = position, now
        if self.track:
            self.overlay.display(self.track.text_at(position))
            return
        audio_stream = "0:a:0"
        try:
            tracks = service.audioTracks()
            selected = tracks.getCurrentTrack()
            pid = int(tracks.getTrackInfo(selected).getPID())
            if 0 < pid <= 8191:
                audio_stream = "0:i:0x%X" % pid
            elif selected >= 0:
                audio_stream = "0:a:%d" % selected
        except (AttributeError, TypeError, ValueError):
            pass
        if self.audio_stream is not None and audio_stream != self.audio_stream:
            self.generation += 1
            self.scheduler.reset()
        self.audio_stream = audio_stream
        self.runtime.command(path, settings.target.value, settings.model.value, self.generation, position, audio_stream,
            self.preview_position if self.preparing is not None else None, int(settings.startup_delay.value) * 1000)
        if state.get("error") != self.last_error:
            self.last_error = state.get("error")
            if self.last_error:
                logger().warning("Subtitle status: %s", self.last_error)
        if self.preparing is not None:
            self.overlay.hide()
        elif state.get("generation") == self.generation:
            correction = int(float(settings.sync.value) * 1000)
            if correction != self.correction:
                self.scheduler.reset()
                self.correction = correction
            cues = split_cues(state.get("cues", []), self.overlay.line_chars)
            self.overlay.display(self.scheduler.refresh(cues, position, correction))
        else:
            self.overlay.hide()

    def stop_translation(self, reason):
        active = settings.enabled.value or self.runtime is not None or self.overlay is not None
        settings.enabled.value = False
        settings.enabled.save()
        self.timer.stop()
        runtime, self.runtime = self.runtime, None
        if runtime is not None:
            runtime.stop()
        self.clear()
        self.path = None
        self.last_error = None
        if active:
            logger().info("Translation stopped: %s", reason)

    def stop(self):
        self.cancel_connection_test()
        self.stop_translation("Enigma2 shutdown")
        if self.standby_counter is not None:
            self.standby_counter.removeNotifier(self.enter_standby)


monitor = None


def shutdown():
    global monitor
    if monitor is not None:
        monitor.stop()
        monitor = None


def main(session, **kwargs):
    global monitor
    if monitor is None:
        settings.enabled.value = False
        settings.enabled.save()
        monitor = PlaybackMonitor(session)

    def selected(reference=None):
        if reference is not None:
            try:
                from Screens.MoviePlayer import MoviePlayer
            except ImportError:
                from Screens.InfoBar import MoviePlayer
            session.open(MoviePlayer, reference)
    session.openWithCallback(selected, SettingsScreen)
