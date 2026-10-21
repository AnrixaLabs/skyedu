#!/usr/bin/env bash
# SkyED v2.2.25: renderer-only deploy/rollback. Never edits posts, DB or media.
set -Eeuo pipefail
umask 077
ROOT=/var/www/skyed.org
PLUGIN="$ROOT/wp-content/plugins/skyed-lesson-renderer"
PHP="$PLUGIN/skyed-lesson-renderer.php"
BASE=/var/www/.skyed-renderer-v225
OLD=fa9a75ec06cb20f4b1127488564c7d19572ccd4b195b329f27694876d0d676e9
NEW=e842bc38ea61130496613f1f872112feb9459a044613d3874ad17f464873929c
ZIPHASH=4a733f9f20b9b02c03cc904e06ae3b3b1a25cee9970775b7823c43ce1d25fab2
MODE="${1:-inspect}"
ID="${2:-}"
[[ "$ID" =~ ^[a-f0-9]{16}$ ]] || { echo STATUS=BLOCKED_INVALID_ID; exit 10; }
RUN="$BASE/$ID"
INPUT="/tmp/skyed-v225-$ID.zip"
hash_file() { sha256sum "$1" | awk '{print $1}'; }
fail() { echo "STATUS=BLOCKED_$1"; exit 12; }
fpm_ok() {
  [[ "$(id -u www-data)" == 33 ]] &&
  runuser -u www-data -- test -x "$PLUGIN" &&
  runuser -u www-data -- test -r "$PHP" &&
  runuser -u www-data -- test -r "$PLUGIN/assets/skyed-lesson.css"
}
identity() {
  [[ "$(realpath "$ROOT")" == "$ROOT" && -f "$ROOT/wp-config.php" ]] || fail ROOT
  [[ -d "$PLUGIN" && ! -L "$PLUGIN" && -f "$PHP" ]] || fail PLUGIN
  command -v wp >/dev/null && command -v flock >/dev/null && command -v runuser >/dev/null || fail TOOLS
  [[ "$(wp --allow-root --path="$ROOT" config get DB_NAME 2>/dev/null)" == skyed_org ]] || fail DB
  [[ "$(wp --allow-root --path="$ROOT" db prefix 2>/dev/null)" == wpml_ ]] || fail PREFIX
}
http_ok() {
  local page html
  for page in lesson181 lesson182; do
    html="$(curl -fsSL --max-time 40 --connect-timeout 10 \
      "https://skyed.org/en/$page/?release_probe=$ID")" || return 1
    [[ "$html" == *skyed-lesson* && "$html" == *skyed-practice* ]] || return 1
  done
}
restore() {
  [[ -f "$RUN/original/skyed-lesson-renderer.php" ]] || { echo STATUS=ROLLBACK_MISSING_ORIGINAL; return 1; }
  [[ "$(hash_file "$RUN/original/skyed-lesson-renderer.php")" == "$OLD" ]] || { echo STATUS=ROLLBACK_BACKUP_HASH_MISMATCH; return 1; }
  local now
  now="$(hash_file "$PHP")"
  if [[ "$now" == "$OLD" ]]; then
    touch "$RUN/ROLLED_BACK"
    echo STATUS=RESTORED_V047_VERIFIED
    return 0
  fi
  [[ "$now" == "$NEW" && ! -e "$RUN/rejected-candidate" ]] || { echo STATUS=ROLLBACK_CONCURRENT_CHANGE; return 1; }
  mv "$PLUGIN" "$RUN/rejected-candidate"
  mv "$RUN/original" "$PLUGIN" || { echo STATUS=ROLLBACK_MOVE_FAILED; return 1; }
  [[ "$(hash_file "$PHP")" == "$OLD" ]] && fpm_ok || { echo STATUS=ROLLBACK_VERIFY_FAILED; return 1; }
  touch "$RUN/ROLLED_BACK"
  echo STATUS=RESTORED_V047_VERIFIED
}
if [[ "$MODE" == watchdog ]]; then sleep 720; fi
mkdir -p "$BASE"
chmod 700 "$BASE"
exec 9>"$BASE/lock"
flock -w 90 9 || fail CONCURRENT_TRANSACTION
identity
CURRENT="$(hash_file "$PHP")"
case "$MODE" in
inspect)
  echo SITE=skyed.org
  echo DB=skyed_org
  echo PREFIX=wpml_
  echo "PHP_SHA256=$CURRENT"
  if fpm_ok; then echo FPM=PASS; else echo FPM=FAIL; fi
  if [[ "$CURRENT" == "$OLD" ]]; then echo STATUS=INSTALLED_V047
  elif [[ "$CURRENT" == "$NEW" ]]; then echo STATUS=INSTALLED_V048
  else echo STATUS=UNKNOWN_PLUGIN_HASH; exit 13; fi
  ;;
deploy)
  [[ "$CURRENT" == "$OLD" ]] || fail NOT_ORIGINAL
  fpm_ok || fail ORIGINAL_FPM
  [[ -f "$INPUT" && "$(hash_file "$INPUT")" == "$ZIPHASH" ]] || fail CANDIDATE_ZIP
  [[ ! -e "$RUN" ]] || fail TRANSACTION_EXISTS
  mkdir -m 700 "$RUN"
  mv "$INPUT" "$RUN/candidate.zip"
  cp -a "$PLUGIN" "$RUN/backup"
  [[ "$(hash_file "$RUN/backup/skyed-lesson-renderer.php")" == "$OLD" ]] || fail BACKUP_HASH
  mkdir "$RUN/extracted"
  unzip -qq "$RUN/candidate.zip" -d "$RUN/extracted"
  STAGED="$RUN/extracted/skyed-lesson-renderer"
  [[ -d "$STAGED" && ! -L "$STAGED" ]] || fail ZIP_LAYOUT
  [[ -f "$STAGED/skyed-lesson-renderer.php" && -f "$STAGED/assets/skyed-lesson.css" ]] || fail ZIP_CONTENTS
  [[ "$(hash_file "$STAGED/skyed-lesson-renderer.php")" == "$NEW" ]] || fail CANDIDATE_PHP_HASH
  php -l "$STAGED/skyed-lesson-renderer.php" >/dev/null || fail PHP_SYNTAX
  # Preserve the working plugin's FPM-compatible owner/group and permissions.
  chown -R --reference="$PLUGIN" "$STAGED"
  find "$STAGED" -type d -exec chmod "$(stat -c %a "$PLUGIN")" {} +
  find "$STAGED" -type f -exec chmod "$(stat -c %a "$PHP")" {} +
  chmod "$(stat -c %a "$PLUGIN/assets")" "$STAGED/assets"
  chmod "$(stat -c %a "$PLUGIN/assets/skyed-lesson.css")" "$STAGED/assets/skyed-lesson.css"
  runuser -u www-data -- test -r "$STAGED/skyed-lesson-renderer.php" || fail STAGED_FPM
  runuser -u www-data -- test -r "$STAGED/assets/skyed-lesson.css" || fail STAGED_CSS
  cp -a "$0" "$RUN/watchdog.sh"
  chmod 700 "$RUN/watchdog.sh"
  touch "$RUN/PENDING"
  nohup bash "$RUN/watchdog.sh" watchdog "$ID" > "$RUN/watchdog.log" 2>&1 </dev/null 9>&- &
  echo WATCHDOG=ARMED
  mv "$PLUGIN" "$RUN/original"
  if ! mv "$STAGED" "$PLUGIN"; then
    mv "$RUN/original" "$PLUGIN" || true
    echo STATUS=SWAP_UNCONFIRMED
    exit 23
  fi
  if [[ "$(hash_file "$PHP")" != "$NEW" ]] || ! fpm_ok || ! http_ok; then
    restore || exit 24
    echo STATUS=ROLLED_BACK_SERVER_CHECK
    exit 22
  fi
  echo STATUS=PENDING_BROWSER_COMMIT
  ;;
commit)
  [[ -f "$RUN/PENDING" && ! -f "$RUN/COMMITTED" && ! -f "$RUN/ROLLED_BACK" ]] || fail NO_PENDING_COMMIT
  [[ "$CURRENT" == "$NEW" ]] && fpm_ok && http_ok || fail COMMIT_VERIFICATION
  touch "$RUN/COMMITTED"
  echo STATUS=COMMITTED_V048
  ;;
rollback)
  [[ -f "$RUN/PENDING" && ! -f "$RUN/COMMITTED" ]] || fail ROLLBACK_NOT_ELIGIBLE
  restore
  ;;
watchdog)
  [[ -f "$RUN/PENDING" ]] || exit 0
  [[ ! -f "$RUN/COMMITTED" && ! -f "$RUN/ROLLED_BACK" ]] || exit 0
  restore || echo STATUS=WATCHDOG_RESTORE_UNCONFIRMED
  ;;
*) fail UNKNOWN_MODE ;;
esac
