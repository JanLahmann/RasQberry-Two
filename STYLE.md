# Writing style for rasqberry.org

Every page on this site follows these rules. Ket's summaries use them too.

## Goal

A visitor grasps the essentials in seconds, sees how much RasQberry can do, and wants to
build one. Pages give the overview; details live on detail pages, and questions go to Ket.

## Reader

Curious newcomers: teachers, students, makers, workshop guests. No quantum or Linux
knowledge assumed. Experts follow the links.

## Voice

- Friendly, direct, inviting. Address the reader as "you".
- Spark the wish to build and try it: lead with what you can do and see, not with setup.
- Concrete, not hype ("revolutionary", "amazing"): let images and real features impress.
- RasQberry is a community project: never imply IBM endorses or supports it.

## Language

- English, American spelling.
- Short sentences, active voice, present tense. One idea per sentence.
- Explain a technical term in half a sentence the first time it appears on a page.

## Page shape

1. One sentence: what this is and what it is for.
2. What you can do: bullets, one line each, with a link.
3. Steps: commands in code blocks, menu paths in bold with →
   (**0 RasQberry** → **System Info**).
4. The page layout ends each page with "Questions? Ask Ket"; don't add it yourself.
   Not on the privacy, testing and 404 pages (`NO_ASK_KET` in PageLayout).

## Rules

- Scannable: headings, short bullets and images carry the page; a reader who only skims them
  still gets the message.

- Each fact lives on one page; everywhere else links to it.
- Mention every capability once, in one line, on the page that owns it.
- Compute every number; never estimate counts, sizes or times.
- Avoid text that goes stale (dates, version numbers) unless the reader needs it.
- Up to about 600 words per page. Reference pages (bill of materials, assembly guide, details pages,
  testing) may be longer but follow the same shape.
- Privacy and legal text changes only with the maintainer's explicit OK.

## Images

- Show, don't describe: a screenshot or photo wherever the reader has to find something on
  screen or on the hardware, and one image per demo.
- Screenshots come from a real Pi running the current image, cropped to what matters.
- Every image has alt text that says what it shows.
- No personal data in images: hostnames, IP addresses, Wi-Fi names, user names, tokens.
- Folders: `public/installation-images/` (setup and menus), `public/demo-screenshots/`
  (demos), `public/assembly-images/` (hardware). WebP or PNG, aim for under 300 KB each.

## FAQ

`content/faq.md` holds answers written by the maintainer, so the site and Ket give the same
answer. Each entry: a general question (never a visitor's own words), a 2–4 sentence answer,
and the date it was written.
