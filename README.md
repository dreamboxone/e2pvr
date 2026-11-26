<h1 align="center">
  <img alt="E2PVR" src="src/E2PVR/plugin.png" width="260">
</h1>

<p align="center" dir="rtl"><b>ترجمهٔ زیرنویس فیلم‌های ضبط‌شده در Enigma2</b></p>

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

## فارسی

E2PVR صدای فیلم ضبط‌شده را از طریق Gemini Live ترجمه می‌کند و زیرنویس را روی تصویر نمایش می‌دهد. ریسیور به اینترنت، FFmpeg و کلید معتبر Gemini API نیاز دارد.

### نصب

بستهٔ مناسب را از صفحهٔ انتشارها دانلود کنید، با نام اصلی به پوشهٔ `/tmp` ریسیور منتقل کنید و با حساب `root` از طریق SSH وارد ریسیور شوید. هنگام اجرا، فقط یک فایل نصب E2PVR از نوع انتخاب‌شده در `/tmp` قرار دهید. [دانلود بسته‌ها](https://github.com/dreamboxone/e2pvr/releases/latest)

**DreamOS با بستهٔ DEB**

```sh
dpkg -i /tmp/enigma2-plugin-extensions-e2pvr_*.deb
```

**ایمیج‌های مبتنی بر opkg با بستهٔ IPK**

```sh
opkg install /tmp/enigma2-plugin-extensions-e2pvr_*.ipk
```

پس از نصب، رابط Enigma2 دوباره راه‌اندازی می‌شود و فایل نصب از `/tmp` پاک می‌شود. کلید Gemini API را به‌تنهایی در یک خط در فایل مربوط به بسته قرار دهید.

- DEB: فایل `/root/apikey.txt`
- IPK: فایل `/home/root/apikey.txt`

### حذف افزونه

**روی DreamOS**

```sh
dpkg -r enigma2-plugin-extensions-e2pvr
```

**روی ایمیج‌های مبتنی بر opkg**

```sh
opkg remove enigma2-plugin-extensions-e2pvr
```

پس از حذف، رابط Enigma2 را دوباره راه‌اندازی کنید. فایل کلید API برای نصب‌های بعدی حفظ می‌شود.

### استفاده

1. یک فیلم ضبط‌شده را از PVR پخش کنید و **E2PVR** را از منوی **Plugins** یا **Extensions** باز کنید.
2. زبان برنامه و زبان زیرنویس را جداگانه انتخاب کنید. با دکمهٔ **زرد** می‌توانید اتصال به سرویس ترجمه را آزمایش کنید.
3. دکمهٔ **قرمز** ترجمه را شروع می‌کند و تنظیمات را ذخیره می‌کند. اگر فیلمی در حال پخش نباشد، فهرست ضبط‌ها برای انتخاب فیلم باز می‌شود.
4. برای توقف، دوباره E2PVR را باز کنید و دکمهٔ **آبی** را بزنید. دکمهٔ **سبز** تنظیمات را ذخیره می‌کند و **Exit** از تغییرات ذخیره‌نشده صرف‌نظر می‌کند.
5. استندبای ترجمه را متوقف می‌کند. پس از بیدار شدن ریسیور، برای شروع دوباره **قرمز** را بزنید.

برای دیدن آخرین پیام‌های لاگ این دستور را روی ریسیور اجرا کنید.

```sh
tail -n 100 /tmp/e2pvr.log
```

</div>
