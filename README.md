# FORMA — online coaching intake

A client intake form and a private coach console. Static site: no server, no build step,
no monthly cost. Publish it on GitHub Pages and it runs off Google Sheets.

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
back button.
