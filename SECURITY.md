# Security Policy

## Reporting a security issue

Do not publish credentials, tokens, private keys, personal data, or exploit details in a public issue.

Report security-sensitive findings privately to the repository owner through GitHub. If GitHub private security reporting is enabled for this repository, use that channel.

## Credential handling

This repository is public. Treat every committed file as publicly readable.

- Keep real credentials only in local secret storage or deployment secret managers.
- Use `.env.example` for variable names and non-secret examples only.
- Never commit `.env`, local GUI configuration, SSH keys, application passwords, API tokens, or signing material.
- Rotate any credential immediately if it is accidentally committed, even if the file is subsequently deleted.
- Removing a secret from the current branch does not remove it from Git history.

## Supported code

Security fixes should target the current default branch unless a maintained release branch is explicitly documented.
