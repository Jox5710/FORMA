# FORMA — online coaching intake

A client intake form and a private coach console. Static site: no server, no build step,
no monthly cost. Publish it on GitHub Pages and it runs off Google Sheets.

Read a client's file, write their diet and training plans next to it, and send the finished
plan to them as a PDF — without leaving the page.

## Files

| File | What it is |
|---|---|
| `index.html` | The client form. This is the link you send to clients. |
| `dashboard.html` | Your private console. Keep this link to yourself. |
| `setup.html` | The 6-minute Google Drive setup guide, including the Apps Script to paste. |
| `support.js` | Required runtime. Upload it too. |
| `vendor/` | React, served from your own site instead of a CDN. Upload it too. |
| `assets/` | Your photos, cut out and optimised — 27 files, 850KB in total. Upload it too. |
| `apps-script.gs` | A copy of the backend code, for pasting into Apps Script. `setup.html` shows the same thing with a Copy button. |
| `tools/build-assets.py` | Rebuilds `assets/` from your originals. Never needs to run on the server. |
| `tools/build-cuts.py` | Rebuilds `assets/cut-*.webp` from `forma_cuts/`. Also never runs on the server. |
| `images/` | The full-size originals. **Not** uploaded, and gitignored — 172MB of 4000×3000 phone shots. |
| `forma_cuts/` | The background-removed poses as they arrived. **Not** uploaded, and gitignored — 26MB. |

## Your photos

`tools/build-assets.py` turns the shots in `images/` into everything the site
uses. It cuts you out of three of them with a local segmentation model, so the
portraits sit on the dark background with no white box around them, finds your
head for the round avatar, and crops eight more into a gallery. Every photo off
a phone is stored sideways with an orientation flag, which the script applies —
ignore it and everyone ends up lying down.

To swap a photo, edit the lists at the top of the script and re-run it:

```bash
pip install pillow opencv-python onnxruntime
mkdir -p ~/.u2net && curl -L -o ~/.u2net/isnet-general-use.onnx \
  https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx
python3 tools/build-assets.py
```

### The poses

`forma_cuts/` holds thirteen shots with the background already taken off — but
saved as JPEG, which has no alpha channel, so the checkerboard an editor draws to
mean "transparent" is baked into the pixels. Used as they arrive, every one shows
a grey grid behind you. `tools/build-cuts.py` rebuilds the real transparency:

```bash
python3 tools/build-cuts.py
```

It cannot simply key the checkerboard out — that pattern is two near-greys, and so
are black shorts, so a colour key takes the shorts with it. It runs the same
segmentation model the rest of the pipeline uses, which finds the person and
ignores whatever is behind them, then crops each pose to its own edges.

Where they show up: your original cutout still leads the intake form; the thirteen
poses stand on branded panels — four under *Who you'll be training with*, one
beside the console's connect card, one on the setup page, one on every plan cover,
one at the head of each training day, and three closing every plan. Your face is
the avatar on both pages and beside your notes in each plan.

Only six of the thirteen are named in `dashboard.html`'s `CUT_SRC`, because each
one is embedded into every plan you export. The other seven cost nothing until you
put them in that line, so swapping a pose is a one-line edit.

## Your logo

The mark in `images/brand/` becomes four things: the tab icon, the home-screen
icon, the logo in every page header and on the exported plans, and the animation
on the loading screen.

Both originals are far too heavy to publish — the animation alone arrived at
3.8MB, which would have made the loading screen the slowest thing on the site. It
ships as a 55KB animated WebP instead: cropped to the part that actually moves,
a third of the frames, ten a second. The tab icon is cropped to where the ink is
rather than fitted whole, because a tall mark centred in a square turns to mush
at 16px, and it is inlined into each page as a data URI so it costs no request.

To swap either, replace the file in `images/brand/` and run:

```bash
python3 tools/build-assets.py brand
```

## The only thing to edit

Both pages have one line near the top of their script block:

```js
const API_URL = "https://script.google.com/macros/s/…/exec";
```

Paste your Google Apps Script Web App URL there — same URL in both files. That is the
whole configuration. The dashboard then asks you for nothing but your access code, which
is stored on your device and never appears in the published files.

Optional, in `index.html`:

```js
const COACH_WHATSAPP = "+20…";   // adds a message button to the thank-you screen
```

Full instructions: open `setup.html`.

## Publish

Upload every file — including `support.js` and the `vendor` folder — to a GitHub repo,
then **Settings → Pages → Branch: main → Save**.

- Send clients to `yourname.github.io/forma/`
- Keep `yourname.github.io/forma/dashboard.html` for yourself

## What is in this version

**Sending is reliable.** Google Apps Script answers a POST with a redirect the browser
usually refuses to let the page read. The old code either hung on "Sending…" forever or
claimed the send had failed for a file that had already landed in the sheet. Now a
watchdog always releases the button, an unreadable response while online counts as
delivered, a genuinely offline device says so and queues the file for automatic sending
later, and every submission carries a `submissionId` so a retry can never create a
duplicate row.

**The form checks its answers without arguing.** Names, WhatsApp numbers, emails, ages,
heights, weights, sleep hours and step counts are format- and range-checked, Arabic-Indic
numerals included, and phone numbers are normalised to international form so the WhatsApp
links in your console always work. What is compulsory is only what makes a file usable:
their name, how to reach them, their measurements, and the one-tap chip groups. **No written
answer is required and none has a minimum length** — "none" is an acceptable answer to what
they have tried before, and ticking an injury invites a description rather than demanding
one. Errors appear under the field itself in the client's language and the page jumps to the
first one.

**Four optional photos.** Front, back, side and an InBody sheet. Each is shrunk on the
client's own phone to about 250KB before it leaves, and they upload one at a time *after*
the answers are already in your sheet — so a photo that fails can never cost you the file.
They land in a private Drive folder, one per client, and the console shows them beside the
intake answers. Nothing is shared by link: your access code is the only way to see them.

**The console is fast.** Search no longer re-serialises every client on every keystroke; it
matches against a prepared index and is debounced. Long lists are windowed, the open client
file is memoised, and the last load is cached so a return visit paints immediately and
refreshes in the background. React is served from `vendor/` rather than a CDN. Keyboard
navigation: `↑ ↓` or `j k` to move, `/` to search, `Esc` to clear.

**Both pages work on a phone.** The form reflows to one column with no sideways scroll and
inputs large enough that iOS will not zoom. The console switches to an inbox layout on
narrow screens: the client list first, tapping a client opens their file full-screen with a
back button. On a phone the page itself scrolls rather than a pane inside it, so the browser
bar collapses and nothing is cut off at the bottom; intake answers stack label-above-value
instead of squeezing into a 140px column; and every console input is 16px, which is what
stops iOS zooming in when you tap the search box.

## Writing plans

Open a client and the file has three tabs: **Intake · Diet plan · Training plan**.

- **Diet.** Daily targets for calories, protein, carbs, fat and water, then meals, then the
  foods in each meal with quantity and macros. Every total works itself out as you type: each
  meal shows its macros and its share of the day, and the day shows how far it is from the
  target — lime inside 5%, orange outside.
- **A meal total you can just write.** Each meal has its own kcal / P / C / F boxes whose
  *placeholder is the figure the foods add up to*. Leave them blank and the foods are added
  up; type over one and yours wins. So a client who does not need every gram weighed can be
  given "620 kcal" and a list of food names. If a typed total and the foods disagree by more
  than a tenth, the editor says what the foods come to rather than quietly picking one.
- **Alternative meals.** Any meal can carry swaps, each a whole meal of its own with its own
  foods, quantities and macros. They print under the meal as **Or instead**, so a client who
  hates tilapia on a Tuesday has somewhere to go. Optional, and off until you add one.
- **Training.** A split, then days, then exercises with sets, reps, rest and tempo. Every
  exercise has a **video link** field; paste a URL and the ▶ next to it lights up so you can
  check the link before the client gets it. Pasting `youtube.com/watch?v=…` without the
  `https://` works — that used to drop the link from the plan silently.
- Their allergies, the foods they will never eat, their injuries and their equipment sit as
  chips above the editor, so you are never writing a plan against answers you cannot see.
- **Start from intake** builds the skeleton from their own answers: their meal count, their
  training days, a protein target from their goal weight.
- Rows can be reordered, duplicated and deleted, and a delete can be undone.

Plans save themselves to the device you write them on, under `forma:plans`. They are **not**
in the Google Sheet, so they do not follow you to another computer. Plans written before
alternatives and meal totals existed still open.

Client photos, unlike plans, do go through the Apps Script — so adding them **does** need one
re-deploy and one fresh authorisation, because writing to Drive is a permission the script
did not have before. `setup.html` says so in step 03.

**Export PDF** prints through the browser, which gives selectable text, a small file and
correctly joined Arabic. **Send on WhatsApp** hands the phone's share sheet a real PDF; on a
desktop, where no browser will let a page attach a file to a chat, it saves the PDF and opens
the chat with the plan written out so you attach it in one drag. HTML and image exports sit
in the same menu, and the image export now saves every page rather than only the first.

**The video button works in the PDF.** The shared PDF is a picture of the page — that is what
keeps Arabic joined — so it carries real PDF link annotations laid over the buttons, and the
address is printed next to the word *Watch* as well, for a client whose reader ignores them
or who prints the sheet on paper.

**Nothing is cut across a page break.** A photo used to arrive as a head on one sheet and a
body on the next. Page breaks are now chosen from the drawing itself: each boundary is walked
backwards until it finds a band of rows that is nothing but background — the gap between two
blocks — and cuts there, where there is nothing to split.

Each plan carries its own EN / ع switch, and an Arabic plan is laid out right-to-left in the
PDF too. **Arabic reads correctly wherever it appears**, whichever way the page is set: an
Arabic meal name or note inside an English plan takes its own direction, and a mixed line
like `8-10 تكرار` keeps its parts in the right order instead of scrambling them.
