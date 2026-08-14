# FORMA - online coaching intake

Static site. No server, no monthly cost.

## Files
- index.html - the client form (send this link to clients)
- dashboard.html - your private console (keep this link to yourself)
- setup.html - the 6-minute Google Drive setup guide
- support.js - required runtime, upload it too

## The only thing to edit
Open index.html in any text editor, find near the top of the script:

    const API_URL = "";

Paste your Google Apps Script Web App URL between the quotes. That is the only edit.
Full instructions: open setup.html.

## Publish
Upload all files to a GitHub repo -> Settings -> Pages -> Branch: main -> Save.
