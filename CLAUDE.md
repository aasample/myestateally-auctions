# MyEstateAlly — Project Guide for Claude

## What This App Is
MyEstateAlly (myestateally.com) is a Flask web app for estate management and downsizing.
It helps families organize belongings, documents, and memories after a loss or during downsizing.
Built and owned by Alicia Baker-Sample (aasample@gmail.com).
**Senior-friendly design is a priority** — larger fonts, high contrast, simple flows.

---

## Deployment Pipeline
**Local worktree → git commit + push → GitHub → then MANUALLY run `gcloud app deploy`**

⚠️ **There is NO auto-deploy from GitHub.** Pushing to GitHub only updates the repo.
You MUST run `gcloud app deploy app.yaml --quiet` from the worktree directory to go live.

- Worktree path: `C:\Users\aasam\.claude-worktrees\myestateally-complete\zen-lovelace`
- Branch: `zen-lovelace`
- GitHub repo: `https://github.com/aasample/myestateally-auctions`
- Live site: `https://www.myestateally.com`
- Google Cloud project: `estateally-ai-services`
- Runtime: Python 3.11, App Engine Standard, instance class F2
- gcloud project already configured: `estateally-ai-services`

**Full deploy sequence after any code change:**
```
git add <files>
git commit -m "message"
git push origin zen-lovelace
gcloud app deploy app.yaml --quiet   ← THIS is what actually goes live
```

Never commit `.env` (gitignored). All secrets live exclusively in Google Cloud Secret Manager.

---

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | Python / Flask |
| Database | Google Cloud Firestore (Native Mode, permanent storage) |
| Hosting | Google Cloud App Engine Standard |
| Auth | Email/password + Google OAuth + MFA (pyotp/TOTP) |
| AI — Item lookup | Gemini 2.5 Flash via REST API (no SDK) |
| AI — Pricing/Vision | OpenAI GPT-4 Vision |
| Email | Gmail SMTP via Flask-Mail |
| Rate limiting | Flask-Limiter |
| Frontend | Vanilla JS — single `MyEstateAllyApp` class in `script.js` |
| CSS | Single `styles.css` — glamour theme (dark navy + gold) |
| PWA | Service worker `sw.js` — caches static files for offline use |

---

## Key Files
```
src/main.py                    — All Flask routes (~7500+ lines, single file)
src/static/script.js           — All frontend JS (single MyEstateAllyApp class)
src/static/styles.css          — All styles (glamour theme appended at bottom)
src/static/sw.js               — Service worker — BUMP VERSION when changing CSS/JS
src/static/family-view.js      — Family sharing view JS
src/templates/index.html       — Main app shell (authenticated users)
src/templates/landing.html     — Public landing page (unauthenticated visitors)
src/templates/mobile-upload.html — QR mobile photo upload page
src/services/storage_service.py — Unified Firestore storage layer
src/utils/validation.py        — Input validation utilities
src/utils/auth_helpers.py      — Authentication helpers
src/utils/decorators.py        — Route decorators (@require_auth etc.)
app.yaml                       — Google Cloud App Engine config (NO secrets here)
requirements.txt               — Python dependencies
```

---

## Secrets — All in Google Cloud Secret Manager
The app uses `get_secret(name)` in `main.py` to fetch secrets at runtime.
Pattern: `value = os.environ.get('KEY_NAME') or get_secret('KEY_NAME')`
**Never put secrets in `app.yaml`, `.env` (committed), or any source file.**

| Secret Name (exact) | What it is |
|---------------------|-----------|
| `OPENAI_API_KEY` | OpenAI API key (Restricted, Model capabilities only) |
| `GEMINI_API_KEY` | Google Gemini AI key |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 Client Secret |
| `MAIL_USERNAME` | Gmail address for outbound email |
| `MAIL_PASSWORD` | Gmail App Password (not the account login password) |
| `BETA_CODE` | Beta access code for new user signups |

---

## CSS Architecture
- **Glamour theme** is at the **bottom** of `styles.css` (dark navy `#0a1628`, gold `#c9a84c`)
- CSS variables used: `--navy`, `--gold`, `--gold-dark`, `--gold-glow`, `--radius-*`, `--spacing-*`
- `styles.css` has an aggressive dark-mode block that forces `color: #fff !important` on all
  `.btn` and `body` — this bleeds into `landing.html` which imports `styles.css`
- **Landing page fix**: `<body class="landing-page">` scopes overrides as `body.landing-page .x`
  giving specificity (0,1,1,0) which beats styles.css's (0,1,0,0) regardless of source order
- **Header**: CSS Grid three-zone layout (`grid-template-columns: auto 1fr auto`)
  — Logo zone | Estate selector (centre) | User menu (right)
- **Mobile ≤768px**: `header-actions` hidden, `mobile-estate-indicator` shown instead
  Uses explicit colours (white text, `var(--gold, #c9a84c)` icon) — not CSS vars that are
  undefined in the glamour theme context (would fall back to transparent)

## Service Worker — IMPORTANT
`sw.js` caches `styles.css` and `script.js`. Browser "Clear Cache" does NOT clear the SW cache.
**Every time you change `styles.css` or `script.js`, bump all three version strings in `sw.js`:**
```javascript
const CACHE_NAME = 'myestateally-v1.0.8';        // ← increment
const STATIC_CACHE = 'myestateally-static-v1.0.8';
const DYNAMIC_CACHE = 'myestateally-dynamic-v1.0.8';
```
Current version: **v1.1.2**
The SW calls `skipWaiting()` on install so the new version activates immediately.

---

## Known Patterns & Gotchas

### Modals
- All modals: `class="modal"` + `style="display:none;"` in HTML
- `.modal { display: none }` in CSS is the hidden default
- JS shows: `modal.style.display = 'flex'` / hides: `modal.style.display = 'none'`
- **Never add a `display` property to a specific modal's CSS class** — it conflicts with
  `.modal { display:none }` since both are specificity (0,0,1,0) and last-in-file wins
- `init()` in `script.js` force-hides all `.modal` elements on startup as a safety net

### Auth & Sessions
- Session keys: `user_id`, `user_email`, `estate_id`, `current_estate_id`
- `@require_auth` decorator checks `session['user_id']`
- `check_permission(estate_id, user_id, action)` gates write operations
- MFA uses TOTP (pyotp) — sessions stored in Firestore with expiry
- Google OAuth uses CSRF state token stored in session

### Firestore Storage
- Collection names: `items`, `estates`, `family_data`, `documents`, `activity_log`, `qr_sessions`
- `storage_service.py` wraps all Firestore reads/writes
- `USE_FIRESTORE=true` in `app.yaml` enables persistent storage (always on in production)

### Bulk Photo Import
- Max 30 photos per batch, rate-limited 20/hr via Flask-Limiter
- Sequential AI processing (one photo at a time) to respect Gemini rate limits
- Reuses `compressItemPhoto()` — HEIC-safe, EXIF-corrected, max 200KB per photo
- 4-step modal: Upload → AI Processing → Review (editable cards) → Done
- Backend endpoint: `POST /api/items/bulk`

### AI Lookup (`/api/ai/lookup-item`)
- Uses Gemini 2.5 Flash via REST (endpoint: `generativelanguage.googleapis.com`)
- Photos capped at 200KB each, max 4 per request
- Strips markdown ` ```json ``` ` fences from response before `json.loads()`
- Defensive parsing: checks `candidates`, `content`, `parts` exist before accessing

### QR Mobile Upload
- `POST /api/qr/generate` — creates a session, returns QR code as base64 PNG
- `POST /api/qr/photo-session` — creates photo-only session, returns `session_id`
- Mobile page: `/qr/upload/<session_id>` — served to mobile device
- `mobile-upload.html` supports `?mode=addphoto` for add-photo-to-item flow
- Desktop polls `GET /api/qr/photo-poll/<session_id>` to detect when photo arrives

---

## Full Project History

### Phase 1 — Initial Setup (Dec 2025)
- Project scaffolded: Flask app, `src/main.py`, basic auth (email + Google OAuth)
- Google Cloud Secret Manager integration for API keys
- Cloud Storage support added, `requirements.txt` established
- Beginner-friendly setup guide, secure secret management

### Phase 2 — Core Features (Dec 2025 – Jan 2026)
- Beta code field on signup, MFA (TOTP) with QR code
- Better onboarding: auto-show create estate modal for new users
- Family roles and permissions system
- Comprehensive estate management features
- AI-powered features (OpenAI integration)
- OpenAI key moved to Secret Manager

### Phase 3 — Firestore Migration (Jan 2026)
- Migrated from JSON file storage to Google Cloud Firestore (Native Mode)
- Phases 1-6: inventory, family, estates, documents, activity log
- Fixed Datastore Mode vs Native Mode confusion
- Fixed OAuth CSRF state mismatch (`SameSite=None` for production)
- Fixed session persistence, Google OAuth redirect loop
- Fixed `estate_storage` deprecation, duplicate session system

### Phase 4 — Security & Quality (Jan–Apr 2026)
- OWASP security fixes (input validation, rate limiting, sanitization)
- Modular architecture: `src/utils/`, `src/services/`
- Automated test suite (19+ tests)
- In-app document preview (PDF + images)
- Fixed AI Lookup: switched Gemini model from `gemini-2.0-flash` to `gemini-2.5-flash`
- Fixed AI Lookup photo compression and iOS HEIC fallback

### Phase 5 — UI/UX Glamour Theme (Apr 2026)
- Full glamour redesign: dark navy header/nav, gold accents, serif fonts
- Header three-zone CSS Grid layout (Logo | Estate | User menu)
- Fixed user menu always invisible (`display:none !important` CSS conflict)
- Quick Actions hover colour changed from blue to gold
- Inventory filter bar standardised to 44px height

### Phase 6 — Bulk Photo Import (Apr–May 2026)
- Bulk Photo Import feature: select up to 30 photos, AI identifies each item
- Editable review cards before saving, progress bar, mobile bottom-sheet
- Mobile "more menu" entry for bulk import
- `POST /api/items/bulk` backend endpoint

### Phase 7 — Bug Fixes & Security (May 2026)
- Fixed bulk modal auto-opening on login (CSS `display` conflict)
- Bumped service worker to v1.0.7 to flush browsers' stale SW cache
- Landing page dark-mode readability: Log In button, hero text, all sections
- Mobile estate indicator: explicit colours (was using undefined CSS variables)
- Removed `GEMINI_API_KEY` from `app.yaml` → Secret Manager only
- Rotated all exposed credentials (OpenAI, Gemini, Google OAuth)
- First successful push to GitHub; Google Cloud deployment pipeline confirmed

### Phase 8 — Glamour Dark Mode Polish (May 2026)
- **Discovered**: GitHub push does NOT auto-deploy — must run `gcloud app deploy app.yaml --quiet` manually every time
- **Fixed bulk modal** (continued): bumped SW v1.0.8; `init()` now sets `visibility:hidden + pointerEvents:none` on all modals so old cached CSS `display:flex !important` cannot keep modal open; `openModal()` and `closeModal()` updated to reset all three properties (display + visibility + pointerEvents)
- **Fixed login button broken**: `openModal()` was not resetting `visibility:hidden` set by `init()`, so auth modal was invisible when Login clicked; SW v1.0.9
- **Fixed secondary buttons invisible on dark navy**: glamour theme applies regardless of OS dark-mode preference; added `body:not(.landing-page) .btn.secondary` to glamour section with translucent-white style; SW v1.1.0
- **Fixed auth modal header invisible**: `.modal-header` now gets explicit dark navy gradient background + white `!important` text + gold icon tint in glamour theme — works in all OS light/dark modes; `closeModal()` and `openModal()` also reset `visibility`/`pointerEvents`; SW v1.1.1
- **Fixed inventory filter selects going white on hover**: `--bg-accent` was `#eff6ff` (near-white), not redefined for dark mode → white text on white bg on hover; added glamour-scoped overrides for all `.inventory-filters select/input` with translucent-white bg, gold border on hover/focus, dark navy option backgrounds; SW v1.1.2

#### Key CSS Lessons (Phase 8)
- The glamour theme is **always active** (plain CSS, not inside a media query). Dark navy look comes from glamour, NOT from `prefers-color-scheme:dark`. Any element that needs to look good on dark navy must have explicit colour rules in the glamour section or be scoped with `body:not(.landing-page)`.
- `body:not(.landing-page)` is the correct scope for app-wide glamour overrides that must not bleed into the landing page.
- `--bg-accent` (#eff6ff) and `--secondary-color` (#f0f9ff) are light-mode values that are NOT redefined in the dark mode `:root` block — never use them for backgrounds in the glamour context.
- All `openModal()` / `closeModal()` calls (both class method and global function) must set `display` + `visibility` + `pointerEvents` together.

---

## Things NOT to Do
- Do not commit `.env` — gitignored for good reason
- Do not put API keys or secrets in `app.yaml`, source files, or markdown docs
- Do not add `display: flex` (or any display value) to modal-specific CSS classes
- Do not use `display: none !important` on elements JS needs to toggle
- Do not assume browser "Clear Cache" fixes SW-cached file issues — bump `sw.js` version
- Do not push without first committing — file edits alone never reach the live site
- Do not skip bumping `sw.js` version when changing `styles.css` or `script.js`
