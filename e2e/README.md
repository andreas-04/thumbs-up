# ThumbsUp E2E Test Suite

End-to-end tests for ThumbsUp using [Playwright](https://playwright.dev/) for browser automation and [Cucumber/Gherkin](https://cucumber.io/) for BDD-style feature specs, bridged by [playwright-bdd](https://vitalets.github.io/playwright-bdd/).

---

## Prerequisites

- **Node.js 20+**
- **Docker** and **Docker Compose** (for the full local stack)
- An already-running ThumbsUp stack, **or** use `docker-compose.test.yml` (see below)

---

## Quick start

### 1. Install dependencies

```bash
cd e2e
npm ci
npx playwright install --with-deps chromium firefox
```

### 2. Start the test stack

From the **repo root**:

```bash
docker compose \
  -f backend/apiv2/docker-compose.yml \
  -f docker-compose.test.yml \
  up -d --build
```

This starts the backend and frontend with:
- A **tmpfs** ephemeral database (clean state every run)
- `ADMIN_PIN=0000`
- `ENABLE_DELETE=true` (needed for file management tests)

Wait until both services are healthy:

```bash
docker inspect --format='{{.State.Health.Status}}' thumbsup-backend
# should print: healthy
wget --spider http://localhost/
```

### 3. Seed test data

```bash
cd e2e
BASE_URL=http://localhost \
  ADMIN_EMAIL=admin@thumbsup.local \
  ADMIN_PASSWORD=admin-secret-pw \
  TEST_USER_EMAIL=testuser@thumbsup.local \
  TEST_USER_PASSWORD=user-secret-pw \
  npx tsx fixtures/seed.ts
```

> **Note**: The admin user must exist in the backend. If the backend starts fresh, create the admin account through the `/signup` endpoint or the admin setup flow first.

### 4. Run the tests

```bash
cd e2e
npm test
```

`npm test` automatically runs `bddgen` to compile feature files into Playwright test specs, then runs Playwright.

Run a specific feature:

```bash
npx bddgen && npx playwright test --grep "Authentication"
```

Open the interactive UI mode:

```bash
npm run test:ui
```

### 5. View the HTML report

```bash
npx playwright show-report
```

---

## Directory structure

```
e2e/
├── features/                  # Gherkin .feature files
│   ├── auth.feature           # Login, logout, invalid credentials
│   ├── signup.feature         # User registration
│   ├── file-browser.feature   # Browse, upload, download
│   ├── admin-dashboard.feature# Admin stats and navigation
│   └── navigation.feature     # Route protection, 404 handling
├── steps/                     # Playwright step definitions
│   ├── auth.steps.ts
│   ├── navigation.steps.ts
│   ├── form.steps.ts
│   └── file.steps.ts
├── fixtures/
│   ├── auth.setup.ts          # Saves login storage state for reuse
│   ├── seed.ts                # Creates test users via API
│   └── .auth/                 # Generated auth state (git-ignored)
├── playwright.config.ts       # Playwright + playwright-bdd configuration
├── tsconfig.json
├── package.json
└── README.md                  # This file
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BASE_URL` | `http://localhost` | URL of the running frontend |
| `ADMIN_EMAIL` | `admin@thumbsup.local` | Admin account email |
| `ADMIN_PASSWORD` | `admin-secret-pw` | Admin account password |
| `TEST_USER_EMAIL` | `testuser@thumbsup.local` | Regular test user email |
| `TEST_USER_PASSWORD` | `user-secret-pw` | Regular test user password |

---

## Tear down

```bash
docker compose \
  -f backend/apiv2/docker-compose.yml \
  -f docker-compose.test.yml \
  down -v
```

---

## CI

The E2E workflow runs automatically on every pull request and push to `main` via `.github/workflows/e2e.yml`. It also runs nightly at 02:00 UTC. Playwright HTML reports and traces are uploaded as workflow artifacts on failure.
