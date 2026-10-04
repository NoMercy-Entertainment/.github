# Retention policy for reusable-cleanup-runs.yml. Sourced; tested by test_cleanup_policy.py.

CANCELLED_MAX_AGE_DAYS=1
FAILED_MAX_AGE_DAYS=7
KEEP_SUCCESSFUL=1
SUCCESS_MAX_AGE_DAYS=14

# Fillz owns these repos and sets their own policy.
SKIP_REPOS="nomercy-ci nomercy-github-runner nomercy-ffmpeg nomercy-ffmpeg-secrets nomercy-whisper-gguf-models nomercy-whisper-models"

# skip_repo <owner/name>: true when the cleanup must leave the repo alone.
skip_repo() {
  local name="${1#*/}" skip
  for skip in $SKIP_REPOS; do
    [ "$name" = "$skip" ] && return 0
  done
  return 1
}

# should_delete <conclusion> <age_days> <successful_seen>
# successful_seen counts this run when it is a success (newest first).
should_delete() {
  local conclusion="$1" age_days="$2" successful_seen="$3"
  case "$conclusion" in
    failure|timed_out|startup_failure)
      [ "$age_days" -ge "$FAILED_MAX_AGE_DAYS" ] ;;
    success)
      [ "$successful_seen" -gt "$KEEP_SUCCESSFUL" ] && [ "$age_days" -ge "$SUCCESS_MAX_AGE_DAYS" ] ;;
    *)
      [ "$age_days" -ge "$CANCELLED_MAX_AGE_DAYS" ] ;;
  esac
}
