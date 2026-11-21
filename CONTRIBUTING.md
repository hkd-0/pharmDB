# Contributing to PharmDB

Thank you for your interest in contributing to PharmDB! To maintain a high standard of code quality and ensure a smooth collaboration workflow, please follow these guidelines.

---

## 🛠️ Getting Started & Environment Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hkd-0/pharmDB.git
   cd pharmDB
   ```

2. **Install pre-commit hooks** (crucial for maintaining code style):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

---

## 🌿 Branching Strategy

We follow a strict **Feature Branch Workflow**:
* `main` branch is protected and reserved for stable, production-ready releases.
* **Never commit directly to `main`.**
* Always create a dedicated feature or fix branch off `main`:
  ```bash
  git checkout main
  git pull origin main
  git checkout -b feat/your-feature-name
  # or
  git checkout -b fix/bug-description
  ```

---

## 📝 Commit Message Guidelines (Conventional Commits)

We use Conventional Commits to keep our git history clean and readable. Format:
`<type>(<scope>): <short description>`

* **`feat`**: A new feature (minor version bump).
* **`fix`**: A bug fix (patch version bump).
* **`docs`**: Documentation only changes.
* **`style`**: Formatting, missing semicolons, etc. (no code changes).
* **`refactor`**: Code changes that neither fix a bug nor add a feature.
* **`test`**: Adding missing tests or correcting existing tests.
* **`chore`**: Changes to build process, CI workflows, or auxiliary tools.

*Example*: `feat(ui): add live search filtering for medicinal products`

---

## 🔀 Pull Request Process

1. Push your feature branch to GitHub:
   ```bash
   git push -u origin feat/your-feature-name
   ```
2. Open a **Pull Request (PR)** targeting the `main` branch.
3. Ensure all **GitHub Actions CI checks** pass successfully (Python syntax checks & Node checks).
4. Review your changes in the PR diff and click **Merge pull request** when ready.
