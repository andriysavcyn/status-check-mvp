# Status Check ✅

> **Deadline tracking & commitment control for cross-functional teams.**  
> Built with FastAPI · SQLAlchemy · SQLite · Vanilla JS · Groq AI

---

## What Is This?

**Status Check** is a lightweight web app for tracking deadlines and commitments made by specialists across different departments or projects. Think of it as a hybrid between a calendar and a task tracker — but the focus isn't on *doing* tasks, it's on *controlling* whether someone else did them.

Every commitment lands on a shared calendar, sorted by deadline. Whoever is responsible for the check-up gets a clear view of what needs their attention and when.

---

## Features

### 🔐 Authentication
- Register / login with username + password
- JWT-based session (HS256, configurable expiry — default 8 hours)
- Passwords hashed with Argon2 via `pwdlib`

### 📅 Shared Calendar View
- Commitments are displayed on a calendar sorted by **deadline date**
- Supports both date-only and datetime deadlines
- Shared across all authenticated users

### 📝 Commitment Management

Each commitment holds:

| Field | Description |
|---|---|
| `title` | Short name of the commitment |
| `description` | Optional longer context |
| `project` | The project or department it belongs to |
| `executor_name` | Person responsible for delivering |
| `checker` | User responsible for verifying (linked to account) |
| `author` | User who created the commitment |
| `deadline` | ISO 8601 datetime or date |
| `created_at` | Auto-set on creation |
| `status` | See statuses below |

Full CRUD: **create · edit · change status · delete**

### 🏷️ Commitment Statuses

| Status | Meaning |
|---|---|
| `to check` | Needs verification in the future |
| `expired` | Deadline passed, no action taken |
| `done` | Verified and closed |
| `not actual` | No longer relevant |
| `ideas backlog` | Idea or tentative plan, not a hard commitment |

### 🔍 Filters
- Filter by **project**
- Filter by **checker** (the person responsible for verification)

### 🤖 AI Smart-Add (Groq / LLaMA 3.3)
Paste a free-text description of a commitment and the AI extracts `title`, `project`, `executor_name`, and `deadline` automatically — powered by Groq's `llama-3.3-70b-versatile` model.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.136, Python 3.13 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (default) / PostgreSQL-ready |
| Auth | JWT (`python-jose`) + Argon2 (`pwdlib`) |
| AI | Groq API via OpenAI-compatible client |
| Frontend | Vanilla JS + HTML/CSS (no build step) |
| Server | Uvicorn (ASGI) |

---

## Getting Started

### Prerequisites
- Python 3.11+
- A [Groq API key](https://console.groq.com/) (optional — only needed for Smart-Add)

### Installation

```bash
# Clone the repo
git clone https://github.com/andriysavcyn/status_check_mvp.git
cd status_check_mvp

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
SECRET_KEY=your-super-secret-key-minimum-32-characters
ACCESS_TOKEN_EXPIRE_MINUTES=480
GROQ_API_KEY=gsk_...          # optional, enables AI Smart-Add
DATABASE_URL=sqlite:///./status_check.db  # or postgresql://...
```

### Run

```bash
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### Demo Users (auto-seeded on first run)

| Username | Password |
|---|---|
| `andrii` | `pass123` |
| `oksana` | `pass123` |
| `markus` | `pass123` |

---

## API Reference

Interactive docs available at `/docs` (Swagger UI) and `/redoc` after starting the server.

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/login` | Login, returns JWT |
| `GET` | `/auth/me` | Get current user |

### Users

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/users/` | List all users (for dropdowns) |

### Commitments

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/commitments/` | Create a commitment |
| `GET` | `/commitments/` | List commitments (supports `?project=` and `?checker_id=`) |
| `GET` | `/commitments/{id}` | Get a single commitment |
| `PUT` | `/commitments/{id}` | Update a commitment |
| `DELETE` | `/commitments/{id}` | Delete a commitment |

### AI

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/parse-text/` | Extract commitment fields from free text |

---

## Project Structure

```
status_check_mvp/
├── app/
│   ├── main.py          # FastAPI app, all routes
│   ├── models.py        # SQLAlchemy ORM models (User, Commitment)
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── database.py      # DB engine & session management
│   └── auth.py          # JWT auth, password hashing, dependencies
├── static/
│   ├── index.html       # Single-page frontend
│   └── style.css        # UI styles
├── requirements.txt
└── .env                 # (not committed) secrets & config
```

---

## Design Decisions

- **SQLite by default** — zero setup for local development; switch to PostgreSQL by changing `DATABASE_URL`.
- **Statuses as a DB enum** — enforced at both the Pydantic and SQLAlchemy layers, preventing invalid state from reaching the database.
- **AI as optional** — the app works fully without a Groq key; Smart-Add is a UX enhancement, not a dependency.
- **No frontend framework** — keeping the stack minimal for an MVP. The entire UI is a single HTML file with no build step.
- **Demo seeding** — on first startup, three demo users are created automatically if the users table is empty.

---

## Roadmap

- [ ] Recurring commitments
- [ ] Email / push notifications before deadline
- [ ] Comments thread per commitment
- [ ] PostgreSQL migration guide
- [ ] Role-based access control (manager vs. executor view)
- [ ] Export to CSV / PDF

---

## License

MIT