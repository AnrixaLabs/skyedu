# SkyEd Bilingual Learning Path (1.0.0)

A self-contained, privacy-first WordPress shortcode with a responsive Chinese/English interface.

## Exactly what it does

- Asks for an age group (3–4, 5–6, or 7–9), existing English experience, learning goal, and session length.
- Builds a four-week home learning activity outline in Simplified Chinese or English.
- Lets visitors change selections and print the plan.
- Stores no child names, audio, emails, answers, or browsing records. There are no API requests from the planner.
- This is **not** a diagnostic assessment, standardized proficiency measurement, or individualized professional evaluation.

## Install on WordPress staging first

1. Package **only** the `skyed-learning-path` folder as `skyed-learning-path.zip`, with the PHP file at the folder root.
2. Back up the WordPress database, uploads, and plugins.
3. In WordPress **Plugins → Add New → Upload Plugin**, upload the ZIP and activate.
4. Create a page for the English tool. Insert a **Shortcode** block containing `[skyed_learning_path lang="en"]`.
5. Create a separate Simplified Chinese page and insert `[skyed_learning_path lang="zh"]`.
6. Test both pages on a mobile device, desktop browser, and keyboard, including form validation, the generated plan, change button and print view.
7. After staging passes, repeat on production and link the two tool pages from Resources / 学习工具.

The shortcode's `lang="auto"` option detects URL prefixes `/zh/` and `/en/`, then falls back to the WordPress locale. Always use an explicit language for independent language pages.

## Operational scope

This plugin provides a bilingual **tool**, not a full Chinese translation of the website. The WordPress theme, Chinese navigation, homepage translations, legal pages, and contact methods must be completed separately in the site CMS.

Do not link to an unverified phone, WeChat, QR code, or email. Replace the current public Contact-page placeholder as a separately verified CMS change.

## QA

Run from repository root:

```bash
php -l wp_plugin/skyed-learning-path/skyed-learning-path.php
node --check wp_plugin/skyed-learning-path/assets/learning-path.js
php tests/learning-path-smoke.php
node --test tests/learning-path.test.cjs
```

For the older lesson renderer, external `data_url` hosts must be explicitly added through `SKYED_PAYLOAD_HOST_ALLOWLIST` in `wp-config.php`. Do not allow internal addresses or untrusted domains.

```php
define('SKYED_PAYLOAD_HOST_ALLOWLIST', ['approved-assets.example.org']);
```

By default, lesson JSON fetches are restricted to the WordPress site's HTTPS host. This is a **breaking security hardening** for previously used external JSON URLs; verify lesson URLs before upgrading the older renderer.
