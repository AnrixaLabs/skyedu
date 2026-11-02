# SkyEd website change report — 2026-11-02

## Verified live website
- Public homepage: https://skyed.cn/ (English)
- Resources: https://skyed.cn/resources/ (mainly informational)
- About: https://skyed.cn/about/ (English)
- Contact: https://skyed.cn/contact/ (publishes an instruction to add a confirmed contact channel)
- Blog: https://skyed.cn/blog/ (English articles)

The current WordPress theme and live CMS content are **not** present in this repository. This branch does not deploy production website changes.

## Implemented on this branch
- Standalone English / Simplified Chinese interactive learning-path WordPress plugin.
- Scoped responsive and printable styles.
- Four-week plan generation covering three age ranges and listening, speaking, or reading goals.
- No collection or storage of child personal information.
- Unit/smoke tests and CI validation.
- Existing renderer hardened: admin-only JSON/text upload overrides, restricted HTTPS trusted-domain JSON loading, bounded response size, short transient cache, JSON script encoding.
- Quiz HTML interpolation escaped and asset path segments validated.
- Health response no longer exposes an absolute server directory.

## Staging / publication gates
1. Validate this branch and its checks, then merge following review.
2. Back up WordPress and inventory existing `skyed_lesson` URLs. Before upgrading renderer check whether any JSON URLs require explicitly approved CDN hosts.
3. Install learning-path plugin ZIP on **staging**; place bilingual shortcodes on distinct pages.
4. Confirm official contact information and replace Contact page placeholder; submit test inquiry through the chosen contact system.
5. Publish fully reviewed `/zh/` and `/en/` site pages. Include nav, site metadata, canonical URLs, hreflang links, privacy notices, and translated articles.
6. Check responsive widths, keyboard navigation, browser compatibility, print output, user-facing errors, caching, and Core Web Vitals.
7. Perform a production backup, deploy via controlled release, smoke test, verify analytics/privacy configuration, and retain rollback instructions.

## Not completed
- No live WordPress theme or page edits (no WordPress administrator access).
- No claim of production security penetration testing, WordPress-version compatibility test, or certified learning assessment.
- No validated public phone, email, or WeChat contact information available to insert.
- No full Chinese website, parent account, or student-data integration implemented.
