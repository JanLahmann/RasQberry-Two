# Privacy

RasQberry has no accounts and sets no cookies. Here is what leaves your browser or your Pi:

- **This website** counts page views and a few clicks (such as "download") with Umami, without cookies and without storing your IP address. It is hosted on GitHub Pages, which keeps server logs like any web host.
- **Ket, the assistant**, only when you open it: your question and the page you are on go to our server (Cloudflare) and on to Anthropic's Claude for the answer. On a Pi, the RasQberry version and Pi model go along. Questions are kept for 30 days, tester notes for 90.
- **The RasQberry Pi** sends anonymous counts: a first start, a daily update check, demo starts and update results, with the RasQberry version, the Pi model and the release channel. No serial number, name or other ID. To switch them off, set `RQ_UMAMI=0` in `/usr/config/rasqberry_environment.env`.
- **Videos** come from YouTube when you play them.

Questions: [open an issue](https://github.com/JanLahmann/RasQberry-Two/issues).
