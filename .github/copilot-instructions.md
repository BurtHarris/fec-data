# Copilot instructions for this repository

Short summary
- Current repository appears empty (no tracked source files found). This file documents detection heuristics and useful conventions to help future Copilot sessions work effectively once code is added.

1) Build / test / lint commands (detection heuristics)
- Repo currently has no package manifests or build files. When files are present, use the following detection order and run commands accordingly:
  - Node (package.json):
    - Install: npm ci
    - Full test: npm test or npm run test
    - Single test: npx jest <path/to/test> -t "test name" OR npm test -- -t "test name"
    - Lint: npm run lint or npx eslint .
  - Python (pyproject.toml, requirements.txt, setup.cfg):
    - Install: python -m pip install -r requirements.txt or python -m pip install -e .
    - Full test: pytest
    - Single test: pytest path/to/file.py::test_function or pytest -k <expr>
    - Lint: ruff . or flake8 .
  - Go (go.mod):
    - Build: go build ./...
    - Full test: go test ./...
    - Single test: go test ./pkg -run TestName
  - Java/Maven (pom.xml):
    - Full test: mvn test
    - Single test: mvn -Dtest=ClassName#method test
  - Gradle (build.gradle):
    - Full test: ./gradlew test
    - Single test: ./gradlew test --tests "com.example.MyTest.testMethod"
  - Makefile: check make help; common targets: make build, make test, make lint
  - Docker/docker-compose: docker-compose up --build for integrated runs

For each detected project type, prefer project-local task runners (npm scripts, tox.ini, Makefile, Gradle wrapper) over global tooling.

2) How to run a single test (quick cheatsheet)
- Jest (Node): npx jest <file> -t "test name"
- Mocha: npx mocha <file> --grep "test name"
- Pytest: pytest path/to/test_file.py::test_name
- Go: go test ./pkg -run TestName
- JUnit/Maven: mvn -Dtest=ClassName#method test

3) High-level architecture (how to discover the big picture)
- Look for these top-level directories in priority order to establish architecture quickly:
  - src/ or lib/ — primary application code
  - cmd/ or cli/ — executable entrypoints
  - pkg/ or internal/ — reusable libraries
  - tests/ or test/ — unit/integration tests
  - data/ or fixtures/ — seeded data or sample CSVs
  - scripts/ or tools/ — maintenance and ETL scripts
  - infra/ or deploy/ — deployment manifests, IaC
- For data-focused repos, expect CSV/TSV in data/ and processing code in scripts/ or src/etl/.
- For multi-language repos, detect each language by its manifest (package.json, pyproject.toml, go.mod) and treat each language subtree as a separate service when reasoning about changes.

4) Key conventions and repository-specific notes
- No repository-specific conventions detected (no README, CONTRIBUTING, or manifest files present). When they exist, prefer using:
  - project-local scripts (npm scripts, Makefile, tox) to run tasks
  - project-defined linters/config files (eslint, ruff, .prettierrc) for formatting/linting rules
- When making changes, search for tests in tests/ or __tests__ to find where behavior is asserted and update tests accordingly.

5) AI / assistant config files checked
- Looked for CLAUDE.md, .cursorrules, AGENTS.md, .windsurfrules, CONVENTIONS.md, AIDER_CONVENTIONS.md, .clinerules — none detected in current tree.

If/when this repository is populated, update this file to include the exact build/test/lint commands discovered in top-level manifests and any repository-specific conventions (naming, API layers, data formats).

---
Created by Copilot session helper. If you'd like, add the repository README/CONTRIBUTING and I will incorporate their contents into this file for more precise instructions.