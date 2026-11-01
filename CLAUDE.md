# CLAUDE.md

Hebrew-language expense tracker: a Telegram bot plus a Streamlit dashboard, used daily by a
small group of real users. `README.md` is the public portfolio write-up; this file is the
working guide.

## Working agreement

- **Ask before changing code.** Explain the change and wait for an explicit "go". A screenshot
  or a question is not approval.
- **Never push to `main` without explicit approval for that specific change.** Pushing to
  `main` deploys to production (see Deploy).
- Answer in Hebrew. Lead with the uncomfortable fact, and mark confidence on claims.

## Architecture

```
Telegram ──▶ new_bot.py (Railway, 24/7 worker) ──▶ Groq API
                     │
                     ▼
              Supabase (Postgres)  ◀── dashboard.py (Streamlit Cloud) ──▶ Groq API
```

The bot and the dashboard never talk to each other. The database is the only integration
point.

Tables: `expenses`, `authorized_users`, `budgets`, `recurring_expenses`, `groups`,
`group_members`, `dashboard_sessions` (schema in `sql/dashboard_sessions.sql`).

### `new_bot.py`

- Input: text → `analyze_text_with_ai`. Voice → Whisper transcription → same path. Photo →
  vision model in `handle_photo`. All three end in `_register_expense`, which saves the
  expense, replies with inline buttons and sends budget alerts at 90% and 100%.
- Auth: `check_auth` checks `authorized_users`. An unknown user must send `ACCESS_PASSWORD`;
  attempts are limited to `MAX_ATTEMPTS`, counted in memory and reset on restart.
- Inline callbacks are routed by prefix: `rec_`, `share_`, `edit_`, `editcat_`, `del_`.
- Scheduled jobs live in `post_init` and use PTB `JobQueue`. Do not use APScheduler: it
  never fired inside PTB's event loop.
  - Recurring reminders: daily at 09:00, plus an hourly safety net. A `last_reminded`
    column holds the month and deduplicates sends.
  - Monthly summary job: daily at 20:00; it only sends on the last day of the month.
  - Budget copy to the new month: daily at 00:10, plus once at startup; it only acts on the
    1st of the month.
- Timezone: `Asia/Jerusalem` (`TZ`) for all dates.
- `CATEGORIES` is a fixed list, duplicated in `dashboard.py`. Keep both copies in sync.
  Append new categories at the end: `editcat_{id}_{index}` stores the list position. Renaming a
  category needs a data migration (see `sql/2026-11_categories.sql`). `CATEGORY_HINTS` tells the
  model which items go where.

### `dashboard.py`

- One large file with 4 tabs, built in `main()`: overview (with the budget section below it),
  expenses table, trends, and "עוד", where a segmented control picks recurring, shared,
  insights or settings. Only the picked section runs. Expanders can't nest, so sections
  that have their own expanders can't go inside one.
- Its own auth: login and registration with the Telegram user ID, SHA-256 password hash,
  and a reset code sent through the bot's `/resetpass`.
- Personal login link ("remember this device"): the bot's `/dashboard [label]` (private chats
  only, no link preview) stores a SHA-256 hash of a random token in `dashboard_sessions` and
  replies with `DASHBOARD_URL?t=<token>`. `main()` checks `?t=` once per session through
  `login_with_token`, which reloads the user row from `authorized_users`. After a token
  login the token is also saved in the browser's `localStorage` through the small custom
  component in `components/browser_storage/`. Chrome's home-screen shortcut opens `/`
  (Streamlit Cloud's manifest `start_url`) without `?t=`, so `main()` reads the stored
  token when the URL has none. Streamlit cannot set an HttpOnly cookie, and cookie
  components fail on Community Cloud. A link expires after 30 idle days or 180 days total.
  "Logout" clears the token from the URL and from `localStorage` but keeps the DB row.
  "Disconnect this device" in settings and the bot's `/logoutall` delete rows. Password
  login stays as is; automated agents use it.
- AI insights and chat use `_groq_chat`, which raises `AIError` with a Hebrew message and
  prints the raw error to the log. The monthly analysis runs only on a button click:
  Streamlit runs every tab's code on each load, so anything automatic in a tab runs on
  every visit.
- Styling: the CSS shared by both themes is in `_common_css(tc())`. Streamlit 1.66 changed
  the DOM. Tabs are `[role="tablist"]` / `[data-testid="stTab"]` (not `data-baseweb`), and
  a selectbox is a react-aria combobox `input`. Plotly charts need `direction: ltr` (the
  global RTL breaks axis labels) and fixed margins, because `automargin` measures 0 for
  charts in hidden tabs. Render charts through `show_chart`, which hides the modebar.
- "Compared to last month" uses `same_period`: in the current month it compares only to
  the same days of the previous month.
- Layout is RTL. The PDF export uses `python-bidi` and Noto Sans Hebrew, downloaded at
  runtime from GitHub into the temp dir (`get_hebrew_font_path`).

## Groq models (the usual source of breakage)

Groq retires models without notice. The API then returns `404 model_not_found`, and the
bot shows a generic error in Telegram.

| Purpose | Env var | Current default |
|---|---|---|
| Text parsing (bot + dashboard) | `GROQ_TEXT_MODEL` | `openai/gpt-oss-120b` |
| Voice transcription | `GROQ_VOICE_MODEL` | `whisper-large-v3` |
| Receipt photos (vision) | `GROQ_VISION_MODEL` | `qwen/qwen3.8-27b` |

- The defaults in code are the source of truth. Railway variables are only for quick
  testing or an emergency swap; remove them once the default in code is updated, so the
  model is never set in two places.
- Retired so far: `llama-3.3-70b-versatile` and `meta-llama/llama-4-scout-17b-16e-instruct`
  (Oct 2026).
- `gpt-oss-*` are text-only reasoning models. Reasoning tokens count toward `max_tokens`,
  so keep the dashboard limit generous.
- The vision model must accept an image and JSON mode in the same request.

### Debugging "the bot shows an error"

1. Check the Groq console → Dashboard → Logs. The model name and error code are shown per
   request.
2. Check the Railway logs. Exceptions are logged by `log.exception(...)` in each handler.
3. The Groq console and `api.groq.com` are blocked from Claude's cloud container. Ask the
   user for screenshots, and have them check model availability in the Playground.

## Deploy and environment

- Bot: Railway runs `worker: python new_bot.py` (`Procfile`) and deploys from `main`.
- Dashboard: Streamlit Community Cloud deploys from `main` and reads Streamlit Secrets.
  `.github/workflows/keep-awake.yml` keeps it awake with Playwright, waiting on
  `domcontentloaded` (not `networkidle`).
- Required env: `TELEGRAM_TOKEN`, `GROQ_API_KEY`, `ACCESS_PASSWORD`, `SUPABASE_URL`,
  `SUPABASE_KEY`. Optional: `DASHBOARD_URL` and the three `GROQ_*_MODEL` variables.
- Python 3.12. `httpx` is pinned to 0.27.2 because of a dependency conflict with
  `python-telegram-bot`.

## Checking changes

There are no tests and no CI that checks code. At minimum, run
`python3 -m py_compile new_bot.py dashboard.py`. Real verification is manual: after a
deploy, the user sends `קפה 15 שקל`, a voice note, or a receipt photo to the bot.
