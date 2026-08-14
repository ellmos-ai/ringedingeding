# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-14

### Added
- Standardized Shields.io badge suite in `README.md` and `README_de.md` (Ecosystem, Umbrella, Python 3.11+, License, Tests, `llms.txt`).
- Machine-readable LLM context file (`llms.txt`) detailing system architecture, module hierarchy, CLI/web entry points, and telephony safety guardrails.
- MIT `LICENSE` file and complete Ruff linter configuration in `pyproject.toml`.
- Architecture & flow Mermaid diagrams in bilingual README documentation.

### Changed
- Refactored Python code to pass all Ruff lint checks with 100% compliance across `ringedingeding/` and `tests/`.
- Ensured 100% test pass rate across all 498 unit, integration, and scenario tests.

### Fixed
- Fixed exception suppression in `cli.py` using `contextlib.suppress`.
- Retained safe SQLite row access patterns in `projects.py`.
