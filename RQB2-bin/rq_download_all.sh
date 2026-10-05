#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Download all demos
# ============================================================================
# Description: Downloads every demo that is not on this Pi yet, so that they
#   start without the internet later (a classroom, a booth). The list comes
#   from the demo manifests, sizes included; the Docker demos are an opt-in
#   second question with their total size (Jan, Q27). One status line per
#   demo with the MB received so far, the small demos first; the details go
#   to a log.
# Usage: rq_download_all.sh                  ask, then download
#        rq_download_all.sh --yes [--docker] no questions (--docker: Docker demos too)
#        rq_download_all.sh --pending        exit 0 if a demo (Docker demos aside) is missing
#        rq_download_all.sh --list           print the missing demos with their sizes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

rq_help_guard "$@"
load_rqb2_env
verify_env_vars REPO USER_HOME

ENGINE="${RQ_DEMO_ENGINE:-$SCRIPT_DIR/rq_demo_run.sh}"   # (override: tests)
SHIPPED_DIR=$(rq_shipped_manifest_dir)
TITLE="Download all demos"

MODE=ask
WITH_DOCKER=ask
for arg in "$@"; do
    case "$arg" in
        --yes) MODE=yes ;;
        --docker) WITH_DOCKER=yes ;;
        --pending) MODE=pending ;;
        --list) MODE=list ;;
        *) die "Unknown option: $arg (see --help)" ;;
    esac
done
[ "$MODE" = yes ] && [ "$WITH_DOCKER" = ask ] && WITH_DOCKER=no

# ----------------------------------------------------------------------------
# What is missing
# ----------------------------------------------------------------------------
# One entry per missing demo, in parallel arrays (bash 3.2 has no maps)
IDS=(); NAMES=(); DOCKER=(); DL=(); DISK=(); PEAK=(); SHARES=(); TIMES=()

docker_ok() {
    command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

# installed MANIFEST TYPE WORKING_DIR MARKER ID
# A checkout is checked here (fast: this runs at every login for the setup
# checklist); Docker demos and the rest ask the demo engine.
installed() {
    local type="$2" wd="$3" marker="$4" id="$5"
    if [ "$type" != "docker" ] && [ -n "$wd" ] && [ -n "$marker" ]; then
        [ -f "$USER_HOME/$REPO/demos/$wd/$marker" ]
        return
    fi
    "$ENGINE" "$id" --is-installed >/dev/null 2>&1
}

collect_missing() {
    local include_docker="$1" mf line id name pre type image repo installer wd marker
    local dl disk peak shares time
    while IFS= read -r mf; do
        [ -n "$mf" ] || continue
        line=$(jq -r '[.id, (.name // .id), (.install.preinstalled // false | tostring),
                       (.entrypoint.type // ""), (.entrypoint.docker_image // ""),
                       (.install.repo_url // ""), (.install.installer // ""),
                       (.entrypoint.working_dir // ""), (.install.marker_file // ""),
                       (.install.download.download_mb // 0 | tostring),
                       (.install.download.disk_mb // .install.download.download_mb // 0 | tostring),
                       (.install.download.peak_mb // 0 | tostring),
                       (.install.download.shares // ""), (.install.download.time // "")]
                      | join("\u001f")' "$mf" 2>/dev/null) || continue
        IFS=$'\037' read -r id name pre type image repo installer wd marker dl disk peak shares time <<< "$line"
        [ "$pre" = "true" ] && continue
        # Something to download: a repo, an installer, or a Docker image
        if [ -z "$repo$installer" ] && { [ "$type" != "docker" ] || [ -z "$image" ]; }; then
            continue
        fi
        if [ "$type" = "docker" ] && [ "$include_docker" != "yes" ]; then
            continue
        fi
        installed "$mf" "$type" "$wd" "$marker" "$id" && continue
        IDS+=("$id"); NAMES+=("$name"); DL+=("$dl"); DISK+=("$disk"); PEAK+=("$peak")
        SHARES+=("$shares"); TIMES+=("$time")
        if [ "$type" = "docker" ]; then DOCKER+=(yes); else DOCKER+=(no); fi
    done < <(rq_list_manifests "$SHIPPED_DIR" 2>/dev/null)
}

# Totals over the entries whose DOCKER value is $1: sets T_DL T_DISK T_PEAK
# T_TIME ("about 2-4 minutes") T_NAMES T_COUNT. Demos that share a download
# count once.
totals() {
    local want="$1" i seen=" " lo=0 hi=0 nums unit lo_m hi_m
    T_DL=0; T_DISK=0; T_PEAK=0; T_NAMES=""; T_COUNT=0; T_TIME=""
    for i in "${!IDS[@]}"; do
        [ "${DOCKER[$i]}" = "$want" ] || continue
        T_COUNT=$((T_COUNT + 1))
        T_NAMES="${T_NAMES:+$T_NAMES, }${NAMES[$i]}"
        if [ -n "${SHARES[$i]}" ]; then
            case "$seen" in *" ${SHARES[$i]} "*) continue ;; esac
            seen="$seen${SHARES[$i]} "
        fi
        T_DL=$((T_DL + DL[i])); T_DISK=$((T_DISK + DISK[i]))
        [ "${PEAK[$i]}" -gt "$T_PEAK" ] && T_PEAK="${PEAK[$i]}"
        # in seconds: "1 minute" -> 60 60, "3-5 minutes" -> 180 300,
        # "10-30 seconds" -> 10 30
        nums=$(printf '%s' "${TIMES[$i]}" | tr -c '0-9' ' ')
        set -- $nums
        if [ $# -ge 1 ]; then
            unit=60
            case "${TIMES[$i]}" in *second*) unit=1 ;; esac
            lo=$((lo + $1 * unit)); hi=$((hi + ${2:-$1} * unit))
        fi
    done
    if [ "$hi" -gt 0 ]; then
        lo_m=$(( (lo + 30) / 60 )); hi_m=$(( (hi + 59) / 60 ))
        [ "$lo_m" -ge 1 ] || lo_m=1
        if [ "$hi" -lt 60 ]; then T_TIME="under a minute"
        elif [ "$hi_m" = 1 ]; then T_TIME="about 1 minute"
        elif [ "$lo_m" = "$hi_m" ]; then T_TIME="about $hi_m minutes"
        else T_TIME="about $lo_m-$hi_m minutes"; fi
    fi
    return 0
}

# "120 of about 900 MB, 45s" while demo INDEX downloads (RX0: rq_rx_mb at its
# start): a 1.3 GB image takes minutes, and seconds alone looked stuck (#28)
progress() {
    local i="$1" rx0="$2" now got=""
    if [ -n "$rx0" ] && now=$(rq_rx_mb) && [ -n "$now" ]; then
        got=$((now - rx0))
        if [ "${DL[$i]}" -gt 0 ] && [ "$got" -le "${DL[$i]}" ]; then
            got="$got of about ${DL[$i]} MB, "
        else
            got="$got MB, "
        fi
    fi
    printf '%s%ds' "$got" $((SECONDS - start))
}

# ----------------------------------------------------------------------------
# Dialogs (whiptail on the terminal; plain text without one)
# ----------------------------------------------------------------------------
TTY="${RQ_TEST_TTY:-/dev/tty}"
have_tty() { { : < "$TTY" > "$TTY"; } 2>/dev/null; }

ask() {   # ask TITLE TEXT [--defaultno]
    local width=72 height
    height=$(_rq_dialog_height "$2" "$width" 12)
    # shellcheck disable=SC2046
    whiptail --title "$1" ${3:-} --yes-button "Download" --no-button "Not now" \
        $(_rq_dialog_scroll "$2" "$width" "$height") \
        --yesno "$2" "$height" "$width" < "$TTY" > "$TTY" 2>&1
}

tell() {  # tell TITLE TEXT
    if [ "$MODE" = ask ] && have_tty && command -v whiptail >/dev/null 2>&1; then
        local width=72 height
        height=$(_rq_dialog_height "$2" "$width" 10)
        # shellcheck disable=SC2046
        whiptail --title "$1" $(_rq_dialog_scroll "$2" "$width" "$height") \
            --msgbox "$2" "$height" "$width" < "$TTY" > "$TTY" 2>&1 || true
    else
        printf '%b\n' "$2"
    fi
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
if [ "$MODE" = pending ]; then
    collect_missing no
    [ "${#IDS[@]}" -gt 0 ]
    exit
fi

if [ "$MODE" = list ]; then
    collect_missing "$(docker_ok && echo yes || echo no)"
    for i in "${!IDS[@]}"; do
        printf '%s\t%s\tdocker=%s\tdownload=%s MB\tdisk=%s MB\n' \
            "${IDS[$i]}" "${NAMES[$i]}" "${DOCKER[$i]}" "${DL[$i]}" "${DISK[$i]}"
    done
    exit 0
fi

if [ "$MODE" = ask ] && { ! have_tty || ! command -v whiptail >/dev/null 2>&1; }; then
    die "Run this in a terminal (it asks before downloading), or use --yes."
fi

[ "$MODE" = ask ] && printf '\nChecking which demos are on this Pi...\n'

if ! rq_reachable "https://github.com"; then
    tell "$TITLE" "No internet connection: github.com cannot be reached.\n\nConnect the Pi to the internet and try again."
    exit 1
fi

DOCKER_AVAILABLE=no
docker_ok && DOCKER_AVAILABLE=yes
collect_missing "$DOCKER_AVAILABLE"

FREE=$(rq_free_mb "$USER_HOME")
if [ "$DOCKER_AVAILABLE" = yes ]; then
    free_docker=$(rq_free_mb /var/lib/docker)
    [ -n "$free_docker" ] && [ "${free_docker:-0}" -lt "${FREE:-0}" ] && FREE="$free_docker"
fi

totals no
G_COUNT=$T_COUNT; G_DL=$T_DL; G_DISK=$T_DISK; G_TIME=$T_TIME; G_NAMES=$T_NAMES
totals yes
D_COUNT=$T_COUNT; D_DL=$T_DL; D_DISK=$T_DISK; D_PEAK=$T_PEAK; D_TIME=$T_TIME; D_NAMES=$T_NAMES

if [ "$G_COUNT" -eq 0 ] && [ "$D_COUNT" -eq 0 ]; then
    note=""
    [ "$DOCKER_AVAILABLE" = yes ] || note="\n\n(Docker is not available, so the Docker demos were not checked.)"
    tell "$TITLE" "All demos are on this Pi already.$note"
    exit 0
fi

WANT_GIT=no
WANT_DOCKER=no
if [ "$MODE" = yes ]; then
    WANT_GIT=yes
    [ "$WITH_DOCKER" = yes ] && WANT_DOCKER=yes
else
    if [ "$G_COUNT" -gt 0 ]; then
        text="Not on this Pi yet ($G_COUNT): $G_NAMES.\n\n"
        text="${text}Download:  about $(rq_fmt_mb "$G_DL") (needs the internet)\n"
        [ -n "$G_TIME" ] && text="${text}Time:      $G_TIME\n"
        text="${text}Free:      $(rq_fmt_mb "${FREE:-0}")\n\n"
        text="${text}Afterwards they start without the internet.\n\nDownload now?"
        ask "$TITLE" "$text" && WANT_GIT=yes
    fi
    if [ "$D_COUNT" -gt 0 ]; then
        if [ "$G_COUNT" -gt 0 ]; then
            text="Also download the Docker demos? They are large:\n$D_NAMES.\n\n"
        else
            text="The other demos are on this Pi. Download the Docker demos too? They are large:\n$D_NAMES.\n\n"
        fi
        text="${text}Download:  about $(rq_fmt_mb "$D_DL") (needs the internet)\n"
        # Docker images share parts: the sum of their sizes is the most they
        # take (14.6 GB listed, about 10 GB used in the user test, #28)
        if [ "$D_COUNT" -gt 1 ]; then
            text="${text}Space:     up to $(rq_fmt_mb "$D_DISK") (the images share parts, so usually less)"
        else
            text="${text}Space:     about $(rq_fmt_mb "$D_DISK")"
        fi
        [ "$D_PEAK" -gt 0 ] && text="${text} ($(rq_fmt_mb $((D_DISK + D_PEAK))) while installing)"
        text="${text}\n"
        [ -n "$D_TIME" ] && text="${text}Time:      $D_TIME\n"
        text="${text}Free:      $(rq_fmt_mb "${FREE:-0}")\n\n"
        text="${text}Without them, each Docker demo downloads on its first start."
        ask "Docker demos too?" "$text" --defaultno && WANT_DOCKER=yes
    fi
fi

[ "$WANT_GIT" = yes ] || [ "$WANT_DOCKER" = yes ] || exit 0

# Free space for everything chosen, with the reserve every download keeps
need=$RQ_SPACE_RESERVE_MB
[ "$WANT_GIT" = yes ] && need=$((need + G_DISK))
[ "$WANT_DOCKER" = yes ] && need=$((need + D_DISK + D_PEAK))
if [ -n "${FREE:-}" ] && [ "$FREE" -lt "$need" ]; then
    tell "$TITLE" "Not enough free space: this needs about $(rq_fmt_mb "$need") (with $(rq_fmt_mb "$RQ_SPACE_RESERVE_MB") to spare), and $(rq_fmt_mb "$FREE") is free.\n\nRemove demos you do not use (Quantum Demos > Remove a demo), or leave out the Docker demos."
    exit 1
fi

# The log lives in the user's cache, owned by the user also when this runs
# as root from the menu
LOG_DIR="$USER_HOME/.cache/rasqberry"
LOG="$LOG_DIR/download-all.log"
run_as_user mkdir -p "$LOG_DIR" 2>/dev/null || mkdir -p "$LOG_DIR"
run_as_user touch "$LOG" 2>/dev/null || touch "$LOG"
printf '\n=== %s: %s ===\n' "$TITLE" "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"

# The question was asked above; the engine still checks the space per demo
export RQ_AUTO_INSTALL=1 RQ_NO_MESSAGES=true

ok=0
failed=""
# The small demos first, the Docker images after them, smallest first: the
# first item was the 1.3 GB Workshop server, the rest waited (#28)
todo=()
for i in $(for i in "${!IDS[@]}"; do
               printf '%s %s %s\n' "${DOCKER[$i]}" "${DL[$i]}" "$i"
           done | sort -k1,1 -k2,2n -k3,3n | awk '{ print $3 }'); do
    if [ "${DOCKER[$i]}" = yes ]; then
        [ "$WANT_DOCKER" = yes ] && todo+=("$i")
    else
        [ "$WANT_GIT" = yes ] && todo+=("$i")
    fi
done

n=${#todo[@]}
if [ "$n" -eq 0 ]; then
    tell "$TITLE" "Nothing to download."
    exit 0
fi
echo
k=0
for i in ${todo[@]+"${todo[@]}"}; do
    k=$((k + 1))
    label="[$k/$n] ${NAMES[$i]}"
    out=$(mktemp)
    start=$SECONDS
    rx0=$(rq_rx_mb) || rx0=""
    "$ENGINE" "${IDS[$i]}" --install-only < /dev/null > "$out" 2>&1 &
    pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        printf '\r%s ... %s   ' "$label" "$(progress "$i" "$rx0")"
        sleep 2
    done
    rc=0
    wait "$pid" || rc=$?
    cat "$out" >> "$LOG"
    if [ "$rc" -eq 0 ] && installed "" "$([ "${DOCKER[$i]}" = yes ] && echo docker)" "" "" "${IDS[$i]}"; then
        printf '\r%s ... done (%ds)                         \n' "$label" $((SECONDS - start))
        ok=$((ok + 1))
    else
        reason=$(sed -n 's/^ERROR: //p' "$out" | tail -n 1)
        printf '\r%s ... failed                              \n' "$label"
        failed="${failed}\n  ${NAMES[$i]}${reason:+: $reason}"
    fi
    rm -f "$out"
done

summary="Downloaded: $ok of $n."
if [ -n "$failed" ]; then
    summary="${summary}\n\nNot downloaded:${failed}\n\nDetails: $LOG\nTry again later; what was downloaded is kept."
else
    summary="${summary} They now start without the internet."
fi
if [ "$D_COUNT" -gt 0 ] && [ "$WANT_DOCKER" != yes ]; then
    summary="${summary}\n\nThe Docker demos download on their first start."
fi
tell "$TITLE" "$summary"
[ -z "$failed" ]
