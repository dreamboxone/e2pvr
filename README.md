<h1 align="center">
  <img alt="E2PVR" src="src/E2PVR/plugin.png" width="260">
</h1>

<p align="center" dir="rtl"><b>ترجمه زیرنویس فیلم‌های ضبط‌شده در Enigma2</b></p>

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

<h2 dir="rtl" align="right">فارسی</h2>

<p dir="rtl" align="right">E2PVR صدای فیلم ضبط‌شده را از طریق Gemini Live ترجمه می‌کند و زیرنویس را روی تصویر نمایش می‌دهد. ریسیور به اینترنت، FFmpeg و کلید معتبر Gemini API نیاز دارد.</p>

<h3 dir="rtl" align="right">نصب</h3>

<p dir="rtl" align="right">بسته مناسب را از صفحه انتشارها دانلود کنید، با نام اصلی به پوشه <code>/tmp</code> ریسیور منتقل کنید و با حساب <code>root</code> از طریق SSH وارد ریسیور شوید. هنگام اجرا، فقط یک فایل نصب E2PVR از نوع انتخاب‌شده در <code>/tmp</code> قرار دهید. <a href="https://github.com/dreamboxone/e2pvr/releases/latest">دانلود بسته‌ها</a></p>

<p dir="rtl" align="right"><strong>DreamOS با بسته DEB</strong></p>

<div dir="ltr" align="left">

```sh
dpkg -i /tmp/enigma2-plugin-extensions-e2pvr_*.deb
```

</div>

<p dir="rtl" align="right"><strong>ایمیج‌های مبتنی بر opkg با بسته IPK</strong></p>

<div dir="ltr" align="left">

```sh
opkg install /tmp/enigma2-plugin-extensions-e2pvr_*.ipk
```

</div>

<p dir="rtl" align="right">پس از نصب، رابط Enigma2 ریبوت میشود و فایل نصب از <code>/tmp</code> پاک می‌شود. کلید Gemini API را به‌تنهایی در یک خط در فایل مربوط به بسته قرار دهید.</p>

<ul dir="rtl" align="right">
  <li dir="rtl" align="right">DEB: فایل <code>/root/apikey.txt</code></li>
  <li dir="rtl" align="right">IPK: فایل <code>/home/root/apikey.txt</code></li>
</ul>

<h3 dir="rtl" align="right">حذف پلاگین</h3>

<p dir="rtl" align="right"><strong>روی DreamOS</strong></p>

<div dir="ltr" align="left">

```sh
dpkg -r enigma2-plugin-extensions-e2pvr
```

</div>

<p dir="rtl" align="right"><strong>روی ایمیج‌های مبتنی بر opkg</strong></p>

<div dir="ltr" align="left">

```sh
opkg remove enigma2-plugin-extensions-e2pvr
```

</div>

<p dir="rtl" align="right">پس از حذف، رابط Enigma2 را دوباره راه‌اندازی کنید. فایل کلید API برای نصب‌های بعدی حفظ می‌شود.</p>

<h3 dir="rtl" align="right">استفاده</h3>

<ol dir="rtl" align="right">
  <li dir="rtl" align="right">یک فیلم ضبط‌شده را از PVR پخش کنید و <strong>E2PVR</strong> را از منوی <strong>Plugins</strong> یا <strong>Extensions</strong> باز کنید.</li>
  <li dir="rtl" align="right">زبان برنامه و زبان زیرنویس را جداگانه انتخاب کنید. با دکمه <strong>زرد</strong> می‌توانید اتصال به سرویس ترجمه را آزمایش کنید.</li>
  <li dir="rtl" align="right">دکمه <strong>قرمز</strong> ترجمه را شروع می‌کند و تنظیمات را ذخیره می‌کند. اگر فیلمی در حال پخش نباشد، فهرست ضبط‌ها برای انتخاب فیلم باز می‌شود.</li>
  <li dir="rtl" align="right">برای توقف، دوباره E2PVR را باز کنید و دکمه <strong>آبی</strong> را بزنید. دکمه <strong>سبز</strong> تنظیمات را ذخیره می‌کند و <strong>Exit</strong> از تغییرات ذخیره‌نشده صرف‌نظر می‌کند.</li>
  <li dir="rtl" align="right">استندبای ترجمه را متوقف می‌کند. پس از بیدار شدن ریسیور، برای شروع دوباره <strong>قرمز</strong> را بزنید.</li>
</ol>

<p dir="rtl" align="right">برای دیدن آخرین پیام‌های لاگ این دستور را روی ریسیور اجرا کنید.</p>

<div dir="ltr" align="left">

```sh
tail -n 100 /tmp/e2pvr.log
```

</div>

</div>
