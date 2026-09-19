# Sky Education — Content Automation Toolkit

Python-based tooling for producing, processing, and publishing digital learning content for Sky Education.

## Status

**Active development toolkit.** The repository contains internal-style automation components, but the repository itself is public. Treat all configuration as public and keep credentials exclusively in local environment files.

## Capabilities

The current codebase includes components for:

- desktop workflow control with PySide6;
- educational content and homework generation;
- image and OCR processing;
- text-to-speech generation;
- WordPress publishing workflows;
- SFTP-based deployment tasks;
- FastAPI/HTTP runtime components;
- reusable quiz/tag assets and templates.

## Technology

- Python 3
- PySide6
- FastAPI + Uvicorn
- Paramiko
- Pillow / OpenCV
- PyMuPDF / Tesseract
- Hugging Face client tooling
- Edge TTS / local TTS support

## Repository layout

```text
assets/             fonts, media and workflow assets
scripts/            supporting automation scripts
skyed/              core Python package/modules
tag_s/              interactive/tag-based learning content
templates/          content templates
wp_plugin/          WordPress integration
pyside_gui.py       desktop application entry point
run_pipeline.py     automation pipeline entry point
.env.example        configuration template
```

## Setup

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a local `.env` from `.env.example` and supply environment-specific values locally.

## Security

Never commit:

- `.env` files;
- API tokens or application passwords;
- SSH/SFTP passwords or private keys;
- local GUI configuration containing credentials;
- IDE workspace metadata containing machine-specific paths.

The repository `.gitignore` is configured to exclude these files. See `SECURITY.md` for reporting and credential-handling guidance.

## Development notes

Generated output belongs under ignored output locations and should not be committed unless it is intentionally part of the source package. Keep deployment configuration environment-specific and avoid embedding production endpoints or credentials in source.

## License

No open-source license is currently included in this repository.

## Ownership

Maintained by **AnrixaLabs** for Sky Education tooling.
