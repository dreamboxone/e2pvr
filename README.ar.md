<h1 align="center">
  <img alt="E2PVR" src="src/E2PVR/plugin.png" width="260">
</h1>

<p align="center" dir="rtl"><b>ترجمة تسجيلات Enigma2 وعرضها كترجمة نصية</b></p>

<p align="center">
  <a href="https://github.com/dreamboxone/e2pvr/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/dreamboxone/e2pvr?style=for-the-badge&amp;color=0b3d91"></a>
  <a href="https://github.com/dreamboxone/e2pvr/releases"><img alt="Total release downloads" src="https://img.shields.io/github/downloads/dreamboxone/e2pvr/total?style=for-the-badge"></a>
  <a href="https://t.me/routekernel1"><img alt="Telegram @routekernel1" src="https://img.shields.io/badge/Telegram-routekernel1-26A5E4?style=for-the-badge&amp;logo=telegram&amp;logoColor=white"></a>
</p>

<p align="center">
  <a href="README.md">فارسی</a> ·
  <a href="README.en.md">English</a> ·
  <a href="README.ar.md">العربية</a>
</p>

<div dir="rtl" align="right">

## العربية

يرسل E2PVR صوت التسجيل إلى Gemini Live ويعرض الترجمة النصية على الشاشة. يلزم اتصال بالإنترنت وFFmpeg ومفتاح Gemini API صالح.

### التثبيت

نزل الحزمة المناسبة من صفحة الإصدارات وانقلها باسمها الأصلي إلى مجلد `/tmp` على جهاز الاستقبال. اتصل بالجهاز عبر SSH بحساب `root`. اترك في المجلد حزمة E2PVR واحدة فقط من النوع الذي ستثبته. [تنزيل الحزم](https://github.com/dreamboxone/e2pvr/releases/latest)

**DreamOS باستخدام حزمة DEB**

```sh
dpkg -i /tmp/enigma2-plugin-extensions-e2pvr_*.deb
```

**صور Enigma2 التي تستخدم opkg**

```sh
opkg install /tmp/enigma2-plugin-extensions-e2pvr_*.ipk
```

بعد التثبيت، تعاد تهيئة واجهة Enigma2 ويحذف ملف التثبيت من `/tmp`. ضع مفتاح Gemini API وحده في سطر واحد في الملف المناسب لحزمتك.

- حزمة DEB تستخدم الملف `/root/apikey.txt`
- حزمة IPK تستخدم الملف `/home/root/apikey.txt`

### إزالة الإضافة

**DreamOS**

```sh
dpkg -r enigma2-plugin-extensions-e2pvr
```

**صور Enigma2 التي تستخدم opkg**

```sh
opkg remove enigma2-plugin-extensions-e2pvr
```

أعد تشغيل واجهة Enigma2 بعد الإزالة. يبقى ملف مفتاح API محفوظا للتثبيت لاحقا.

### الاستخدام

1. شغل تسجيلا من PVR، ثم افتح **E2PVR** من قائمة **Plugins** أو **Extensions**.
2. اختر لغة الواجهة ولغة الترجمة كلا على حدة. اضغط الزر **الأصفر** لاختبار الاتصال بخدمة الترجمة.
3. اضغط الزر **الأحمر** لبدء الترجمة وحفظ الإعدادات. إذا لم يكن هناك تسجيل قيد التشغيل، ستظهر قائمة التسجيلات لاختيار أحدها.
4. لإيقاف الترجمة، افتح E2PVR واضغط الزر **الأزرق**. يحفظ الزر **الأخضر** الإعدادات، ويلغي زر **Exit** التغييرات غير المحفوظة.
5. يتوقف عمل الترجمة أثناء وضع الاستعداد. اضغط الزر **الأحمر** بعد إيقاظ الجهاز لبدء الترجمة مجددا.

لعرض آخر رسائل السجل، نفذ هذا الأمر على جهاز الاستقبال.

```sh
tail -n 100 /tmp/e2pvr.log
```

</div>
