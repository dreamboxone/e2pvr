# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
import os
import sys
import textwrap
import threading
from xml.sax.saxutils import escape
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import (config, configfile, ConfigSubsection,
    ConfigSelection, ConfigSlider, ConfigYesNo, KEY_LEFT, KEY_RIGHT)
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from enigma import eTimer, getDesktop
try:
    from enigma import addFont
except ImportError:
    addFont = None
from .core import SubtitleTrack, overlay_geometry, logger, steady_time, split_cues, CueScheduler
from .service import KEY_FILE, DEFAULT_MODEL, MODELS, probe, read_key, ServiceError
from .runtime import Runtime
from .live import probe_live
from . import VERSION, PACKAGE_DIR


def native_text(text):
    if sys.version_info[0] == 2 and isinstance(text, unicode):
        return text.encode("utf-8")
    return text


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
    settings.color = ConfigSelection(default="ffffff", choices=[("ffffff", "White"), ("ffff00", "Yellow"), ("00ff00", "Green"), ("00ffff", "Cyan")])
    settings.size = ConfigSelection(default="medium", choices=[("small", "Small"), ("medium", "Medium"), ("large", "Large")])
    fonts = available_fonts()
    settings.font = ConfigSelection(default=fonts[0][0], choices=fonts)
    settings.position = ConfigSlider(default=80, increment=1, limits=(0, 100))
    settings.transparency = ConfigSlider(default=30, increment=5, limits=(0, 100))
if not hasattr(settings, "model"):
    settings.model = ConfigSelection(default=DEFAULT_MODEL, choices=[(model, model) for model in MODELS])
if not hasattr(settings, "sync"):
    settings.sync = ConfigSelection(default="0.00", choices=[("%.2f" % (step / 4.0), "%.2f" % (step / 4.0)) for step in range(-16, 15)])


TRANSLATIONS = {
    "Settings": ("تنظیمات", "الإعدادات"), "Enabled": ("فعال", "تفعيل"),
    "Interface language": ("زبان برنامه", "لغة الواجهة"), "Subtitle language": ("زبان زیرنویس", "لغة الترجمة"),
    "Color": ("رنگ", "اللون"), "Font": ("فونت", "الخط"), "Font size": ("اندازه فونت", "حجم الخط"),
    "Vertical position (%)": ("موقعیت عمودی (درصد)", "الموضع الرأسي (%)"),
    "Box transparency (%)": ("شفافیت کادر (درصد)", "شفافية الإطار (%)"),
    "Subtitle timing (seconds)": ("تنظیم زمان زیرنویس (ثانیه)", "توقيت الترجمة (ثانية)"),
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
    "Ready - play a recorded movie": ("آماده؛ یک فیلم ضبط‌شده پخش کنید", "جاهز؛ شغّل فيلماً مسجلاً"),
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
            <widget name="save" position="20,%d" size="%d,35" font="Regular;22" foregroundColor="#00ff00" />
            <widget name="cancel" position="%d,%d" size="%d,35" font="Regular;22" foregroundColor="#ff5555" />
            <widget name="test" position="%d,%d" size="%d,35" font="Regular;22" foregroundColor="#ffff00" />
        </screen>''' % (width, height, "".join(columns), height - 140, width - 40, height - 78, width - 40,
            height - 45, width // 3 - 20, width // 3, height - 45, width // 3 - 20,
            2 * width // 3, height - 45, width // 3 - 20)
        Screen.__init__(self, session)
        self.selection = 0
        for index in range(9):
            self["row%d_label" % index], self["row%d_value" % index] = Label(""), Label("")
        self.onLayoutFinish.append(self.refresh_rows)
        self["save"], self["cancel"], self["test"] = Label(""), Label(""), Label("")
        self["status"] = Label("")
        self["publisher"] = Label("Copyright 2026 Routekernel | t.me/routekernel1")
        self.testing = False
        self.test_result = None
        self.test_attempt = 0
        self.timer = eTimer()
        self.connection = bind_timer(self.timer, self.update_test)
        self.onClose.append(self.timer.stop)
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"], {
            "green": self.save, "red": self.toggle_translation, "cancel": self.cancel, "save": self.save,
            "yellow": self.check_connection, "left": self.keyLeft, "right": self.keyRight,
            "up": lambda: self.move(-1), "down": lambda: self.move(1)}, -2)
        self.rebuild()
        self.timer.start(200)

    def toggle_translation(self):
        settings.enabled.value = not settings.enabled.value
        settings.enabled.save()
        configfile.save()
        if monitor:
            monitor.update()
        if settings.enabled.value:
            self.save()
        else:
            self.rebuild()

    def refresh_status(self):
        if self.testing or self.test_result is not None:
            return
        try:
            read_key()
            state = monitor.runtime.state() if monitor and monitor.runtime else {}
            if not settings.enabled.value:
                status = "Translation stopped"
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
        for setting, choices in [(settings.color, [("ffffff", "White"), ("ffff00", "Yellow"), ("00ff00", "Green"), ("00ffff", "Cyan")]),
                                 (settings.size, [("small", "Small"), ("medium", "Medium"), ("large", "Large")])]:
            setting.setChoices([(key, tr(label)) for key, label in choices], default=setting.value)
        self.rows = [("Enabled", settings.enabled), ("Interface language", settings.language),
            ("Subtitle language", settings.target), ("Color", settings.color), ("Font", settings.font),
            ("Font size", settings.size), ("Vertical position (%)", settings.position),
            ("Box transparency (%)", settings.transparency), ("Subtitle timing (seconds)", settings.sync)]
        for name, label in [("save", "Save"), ("cancel", "Stop translation" if settings.enabled.value else "Start translation"), ("test", "Check connection")]:
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

    def refresh_rows(self):
        if not hasattr(self, "rows"):
            return
        from enigma import gRGB
        selected = self.selection
        for index, (label, setting) in enumerate(self.rows):
            self["row%d_label" % index].setText(tr(label))
            if setting is settings.enabled:
                text = tr("Yes" if setting.value else "No")
            elif setting in (settings.position, settings.transparency):
                text = "%d%%" % setting.value
            else:
                text = native_text(setting.getText())
            self["row%d_value" % index].setText(text)
            for name in ("row%d_label" % index, "row%d_value" % index):
                instance = self[name].instance
                if instance:
                    instance.setForegroundColor(gRGB(0x00ffff00 if index == selected else 0x00ffffff))

    def keyLeft(self):
        self.rows[self.selection][1].handleKey(KEY_LEFT)
        self.rebuild()

    def keyRight(self):
        self.rows[self.selection][1].handleKey(KEY_RIGHT)
        self.rebuild()

    def check_connection(self):
        if self.testing:
            return
        self.testing = True
        self.test_attempt += 1
        attempt = self.test_attempt
        self.test_started = steady_time()
        self.test_result = None
        self["status"].setText(tr("Checking connection..."))
        target = settings.target.value
        def check():
            try:
                probe_live(target)
                message = "Connection successful"
            except Exception as error:
                message = str(error)
            if attempt == self.test_attempt:
                self.test_result = message
        thread = threading.Thread(target=check)
        thread.daemon = True
        thread.start()
        self.timer.start(200)

    def update_test(self):
        if self.testing and steady_time() - self.test_started >= 60:
            self.test_attempt += 1
            self.test_result = "Connection test timed out; check receiver network"
        if self.test_result is not None:
            self["status"].setText(tr(self.test_result))
            self.testing = False
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
            <widget name="text" position="10,8" size="%d,%d" font="%s;%d" halign="center" valign="center" transparent="1" noWrap="1" foregroundColor="#%s" />
            <widget name="line2" position="10,%d" size="%d,%d" font="%s;%d" halign="center" valign="center" transparent="1" noWrap="1" foregroundColor="#%s" />
        </screen>''' % (x, y, box_width, box_height, alpha, box_width - 20, box_height // 2 - 8,
                        escape(settings.font.value), points, settings.color.value,
                        box_height // 2, box_width - 20, box_height // 2 - 8,
                        escape(settings.font.value), points, settings.color.value)
        Screen.__init__(self, session)
        self["text"] = Label("")
        self["line2"] = Label("")

    def display(self, text):
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
        self.generation = 0
        self.key_stamp = None
        self.previous_position = None
        self.previous_time = None
        self.preparing = None
        self.paused = None
        self.last_error = None
        self.scheduler = CueScheduler()
        self.correction = None
        self.audio_stream = None
        self.timer.start(100)

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

    def poll(self):
        try:
            self.update()
        except Exception:
            logger().exception("Playback monitor failed")
            self.clear()
            self.path = None
            if self.runtime:
                self.runtime.stop()
                self.runtime = None
            self.timer.stop()

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
        if not path or not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in (".ts", ".mkv", ".mp4", ".avi", ".mov", ".mpg", ".mpeg", ".m2ts"):
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
            if changed_path and not self.track and stamp is not None:
                self.preparing = steady_time()
        service = self.session.nav.getCurrentService()
        seek = service.seek() if service else None
        position_result = seek.getPlayPosition() if seek else (1, 0)
        if position_result[0]:
            if self.preparing is not None and steady_time() - self.preparing >= 4:
                self.release()
            self.overlay.hide()
            return
        position = max(0, position_result[1] // 90)
        now = steady_time()
        state = self.runtime.state()
        if self.preparing is not None:
            if self.paused is None:
                pause = service.pause()
                if pause and pause.pause() == 0:
                    self.paused = pause
                else:
                    self.release()
            if (now - self.preparing >= 4 if self.preparing is not None else False) or state.get("error") or (
                    state.get("generation") == self.generation and state.get("cues")):
                self.release()
        if self.previous_position is not None and self.preparing is None:
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
        self.runtime.command(path, settings.target.value, settings.model.value, self.generation, position, audio_stream)
        if state.get("error") != self.last_error:
            self.last_error = state.get("error")
            if self.last_error:
                logger().warning("Subtitle status: %s", self.last_error)
        if state.get("generation") == self.generation:
            correction = int(float(settings.sync.value) * 1000)
            if correction != self.correction:
                self.scheduler.reset()
                self.correction = correction
            cues = split_cues(state.get("cues", []), self.overlay.line_chars)
            self.overlay.display(self.scheduler.refresh(cues, position, correction))
        else:
            self.overlay.hide()

    def stop(self):
        self.timer.stop()
        self.clear()
        if self.runtime:
            self.runtime.stop()
            self.runtime = None


monitor = None


def session_start(reason, session=None, **kwargs):
    global monitor
    if reason == 0 and session is not None and monitor is None:
        monitor = PlaybackMonitor(session)
    elif reason == 1 and monitor is not None:
        monitor.stop()
        monitor = None


def main(session, **kwargs):
    session.open(SettingsScreen)


def Plugins(**kwargs):
    return [PluginDescriptor(name="E2PVR", description="PVR subtitles", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main),
            PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=session_start),
            PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, fnc=session_start)]
