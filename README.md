# WhatsApp AI Customer-Service Agent — MVP Backend

A working starting point: WhatsApp webhook → intent classification →
catalog lookup / templated reply → human escalation for sensitive cases →
conversation logging for training data collection.

## What's here

```
app/
  main.py        - FastAPI webhook endpoint, ties everything together
  classifier.py  - Keyword-based intent classifier (bootstrap, pre-ML)
  router.py      - Confidence-based routing rules + reply templates
  whatsapp.py    - 360dialog API wrapper (send messages, escalation alerts)
  logger.py      - Logs every message to CSV for later training-data labeling
data/
  catalog.json          - Sample restaurant product/delivery catalog
  conversation_log.csv  - Created automatically once you start receiving messages
test_locally.py  - Run the classifier/router without WhatsApp connected
```

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Test the logic without WhatsApp connected first**
   ```bash
   python test_locally.py
   ```
   This runs sample messages through the classifier and router so you can
   see intents, confidence, entities, and replies before wiring up WhatsApp.

3. **Set up direct access to Meta's WhatsApp Cloud API** (no BSP, no monthly platform fee)
   - Go to [developers.facebook.com](https://developers.facebook.com) → create an app → add the "WhatsApp" product
   - Under **WhatsApp → API Setup**, note your **Phone Number ID** and generate a temporary token to test with
   - For production, create a **System User** (Business Settings → System Users), assign it WhatsApp permissions, and generate a **permanent access token** — temporary tokens from the dashboard expire after 24 hours
   - Copy `.env.example` to `.env` and fill in `WA_ACCESS_TOKEN`, `WA_PHONE_NUMBER_ID`, and `WEBHOOK_VERIFY_TOKEN` (pick any secret string for the latter — you'll enter the same value in Meta's dashboard)

4. **Expose your local server publicly** (360dialog needs a real URL to send webhooks to)
   ```bash
   uvicorn app.main:app --reload --port 8000
   # in another terminal:
   ngrok http 8000
   ```
   Set the ngrok HTTPS URL + `/webhook` as your webhook URL under
   **WhatsApp → Configuration** in the Meta App Dashboard, using the same
   `WEBHOOK_VERIFY_TOKEN` value from your `.env`. Subscribe to the `messages`
   webhook field so incoming customer messages actually get delivered.

5. **Send yourself a test WhatsApp message** to your Meta test number (Meta gives
   you one free test number under WhatsApp → API Setup) and watch the terminal /
   check `data/conversation_log.csv`.
   Note: Meta's test number can only message phone numbers you've explicitly
   added under "To" in the API Setup page, until your app passes review.

## Editing the catalog

`data/catalog.json` is a stand-in for a real product database. For your
first pilot client, replace this with their actual menu/product list —
same structure. Once you have more than one client, this should become
a proper database (SQLite is enough at pilot scale) keyed by `client_id`.

## Upgrading the classifier

`app/classifier.py` is deliberately simple (regex/keyword matching) so you
have something working on day one. Once you've collected 150-300+ real
labeled messages from your pilot (via the conversation log), replace the
`classify()` function with a trained model — the `IntentResult` return
type should stay the same so nothing else needs to change.

## Safety defaults already built in

- `complaint`, `human_handoff_request`, and `dietary_restriction_check`
  **always** escalate to a human, regardless of confidence — never
  auto-answer these, especially for food/health-adjacent businesses.
- Unrecognized messages (low confidence) also escalate rather than
  guessing.

## Confirm/deny follow-up handling

When the classifier is only medium-confidence (0.50-0.85), the bot replies
with its best guess AND asks the customer to confirm ("Did I get that
right? Reply 'yes' to confirm or 'no' to talk to someone.").

- `app/state.py` remembers that this customer has a pending confirmation
  (file-backed JSON, since each webhook call is a fresh HTTP request with
  no memory of the previous turn).
- The next message from that customer is checked against `classify_confirmation()`
  before running the normal classifier:
  - **"yes"** (or "yeah", "ok", "sure", etc.) → confirms and proceeds
  - **"no"** (or "nope", "wrong", etc.) → escalates to a human immediately
  - anything else → treated as a fresh message (the stale pending state is cleared)

Test this flow without WhatsApp connected:
```bash
python test_confirmation_flow.py
```

## Deploying for free (Railway or Render)

Both `Procfile` and `railway.json` are included.

**Railway:**
1. Push this folder to a GitHub repo
2. On railway.app, "New Project" → "Deploy from GitHub repo"
3. Add your `.env` variables under Project → Variables (`WA_ACCESS_TOKEN`, `WA_PHONE_NUMBER_ID`, `WA_GRAPH_VERSION`, `WEBHOOK_VERIFY_TOKEN`, `HUMAN_ESCALATION_NUMBERS`, `BUSINESS_VERTICAL`)
4. Railway auto-detects the `Procfile` — no extra config needed
5. Copy the generated public URL, set `https://<your-app>.up.railway.app/webhook`
   as your webhook URL under **WhatsApp → Configuration** in the Meta App Dashboard

**Render:**
1. Push to GitHub, then "New Web Service" on render.com
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add your `.env` variables under Environment
5. Same as above — use the Render URL + `/webhook` in the Meta App Dashboard

Both have free tiers sufficient for a pilot's traffic volume.

## Next steps

- Swap `data/catalog.json` for your pilot client's real menu/products
- Add a second vertical's catalog structure (fashion: sizes/colors) if
  needed — the classifier already has fashion intents defined
- Move from CSV logging and JSON state to a real database (SQLite is
  enough at pilot scale) once you have multiple concurrent clients
- Once escalated, currently nothing routes the human's WhatsApp reply
  back to the customer automatically — for the pilot, your team can just
  reply to the customer directly from the business's WhatsApp app; a
  proper agent-handoff inbox is a later feature, not an MVP blocker
