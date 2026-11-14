# Privacy

RasQberry has no accounts and sets no cookies. Here is what leaves your browser or your Pi:

- **This website** counts page views and a few clicks (such as "download") with Umami, without cookies and without storing your IP address. It is hosted on GitHub Pages, which keeps server logs like any web host. A few pages show pictures from GitHub or a partner site.
- **Ket, the assistant**, only when you open it: your question, the conversation so far and the page you are on go to our server (Cloudflare) and on to Anthropic's Claude for the answer. On a Pi, the RasQberry version, the Pi model and the LED setup go along. Questions are kept for 30 days. Testers: what we keep is on the [testing page](/testing/#privacy) (90 days).
- **The RasQberry Pi** sends anonymous counts: a first start, a daily update check, demo and learning-path starts, update results and notices, and LED errors, with the RasQberry version, the Pi model, the release channel and the kind of card. No serial number, name or other ID. To switch them off, set `RQ_UMAMI=0` in `/usr/config/rasqberry_environment.env`. The Pi's browser start page is rasqberry.org, so it still counts as a page view.
- **Videos** come from YouTube only when you play them.
- **Your browser** keeps a few settings for this site, such as the assistant's size, or a tester's sign-in until you sign out.

Questions: [open an issue](https://github.com/JanLahmann/RasQberry-Two/issues).
