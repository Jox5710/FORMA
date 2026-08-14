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

**The form checks its answers.** Names, WhatsApp numbers, emails, ages, heights, weights,
sleep hours and step counts are all format- and range-checked, Arabic-Indic numerals
included. Required questions — including the chip groups for gender, goal, training days,
equipment, injuries, conditions, allergies, diet and contact preference — must be answered
before the file can be sent. Errors appear under the field itself in the client's language,
the page jumps to the first one, and phone numbers are normalised to international form so
the WhatsApp links in your console always work.

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
  foods in each meal with quantity and macros. Meal and day totals add themselves up and
  show how far each one is from the target — lime inside 5%, orange outside.
- **Training.** A split, then days, then exercises with sets, reps, rest and tempo. Every
  exercise has a **video link** field; paste a URL and the ▶ next to it lights up so you can
  check the link before the client gets it.
- Their allergies, the foods they will never eat, their injuries and their equipment sit as
  chips above the editor, so you are never writing a plan against answers you cannot see.
- **Start from intake** builds the skeleton from their own answers: their meal count, their
  training days, a protein target from their goal weight.
- Rows can be reordered, duplicated and deleted, and a delete can be undone.

Plans save themselves to the device you write them on, under `forma:plans`. They are **not**
in the Google Sheet, so they do not follow you to another computer — and nothing about the
Apps Script changes, so there is no re-deploy.

**Export PDF** prints through the browser, which gives selectable text, a small file and
correctly joined Arabic. **Send on WhatsApp** hands the phone's share sheet a real PDF; on a
desktop, where no browser will let a page attach a file to a chat, it saves the PDF and opens
the chat with the plan written out so you attach it in one drag. Each plan carries its own
EN / ع switch, and an Arabic plan is laid out right-to-left in the PDF too.
