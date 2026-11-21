# PharmDB 💊

PharmDB is a lightweight, relational pharmaceutical database and management system designed to track drug molecules and medicinal products with seamless synchronization.

[![CI](https://github.com/hkd-0/pharmDB/actions/workflows/ci.yml/badge.svg)](https://github.com/hkd-0/pharmDB/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)
![Status](https://img.shields.io/badge/status-active%20development-orange.svg)

---

## 🌟 Overview

PharmDB bridges the gap between raw molecular data and commercial medicinal products. Built with a decoupled architecture, it features a clean static frontend hosted on modern edge infrastructure and a robust Python backend interfacing with Google Sheets as a relational database.

---

## 🏗️ Architecture & Tech Stack

```text
pharmDB/
├── backend/            # Python HTTP server & database maintenance modules
├── frontend/           # Static web UI (HTML, CSS, modular JS)
├── .github/workflows/  # CI/CD pipelines (GitHub Actions)
└── .pre-commit-config.yaml # Automated code quality hooks
```

* **Frontend**: HTML5, Vanilla JavaScript (modular architecture), CSS3.
* **Backend**: Python 3 (`http.server`), `gspread` (Google Sheets API client), `python-dotenv`.
* **Database**: Google Sheets (Relational tables: `drug_molecule` & `medicinal_product`).
* **Automation & CI**: GitHub Actions, pre-commit (`Black`, `ESLint`).

---

## 🚀 Getting Started Locally

### Prerequisites
* Python 3.10+
* Node.js 18+ (for frontend tooling/checks)
* Git

### 1. Clone the Repository
```bash
git clone https://github.com/hkd-0/pharmDB.git
cd pharmDB
```

### 2. Environment Setup
Create a `.env` file in the root directory with your credentials:
```env
X_API_KEY=your_secure_api_key
SPREADSHEET_ID=your_google_spreadsheet_id
FRONTEND_URL=*
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
```

### 3. Run the Backend Server
```bash
cd backend
python3 server.py
```
*(The server will start on port 8000 by default).*

---

## 📐 Development Workflow & Git Discipline

PharmDB follows strict professional engineering practices:
* **Branching Strategy**: Never commit directly to `main`. Always create feature branches (`feat/` or `fix/`).
* **Conventional Commits**: `<type>(<scope>): <description>` (e.g., `feat(search): add instant autocomplete`).
* **Quality Gates**: Local `pre-commit` hooks format Python code with `Black` and check linting before every commit.

---

## 📦 Versioning

PharmDB adheres to [Semantic Versioning (SemVer)](https://semver.org/).
Current Version: **v0.1.0** *(Pre-release / Evolving Prototype)*.

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
