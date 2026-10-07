# RasQberry: a locale sent by the SSH client that this Pi does not have.
# macOS Terminal sends LC_CTYPE=UTF-8 and sshd accepts LC_*: every login then
# printed "setlocale: LC_CTYPE: cannot change locale (UTF-8)" several times.
# Such a value is replaced with C.UTF-8; locales the Pi has stay as they are.
_a=$(locale -a 2>/dev/null)
if [ -n "$_a" ]; then
    for _v in LC_ALL LC_CTYPE LANG; do
        eval "_l=\${$_v-}"
        [ -n "$_l" ] || continue
        _n=$(printf %s "$_l" | sed "s/UTF-8/utf8/; s/utf-8/utf8/")
        printf '%s\n' "$_a" | grep -qxF "$_n" || export "$_v=C.UTF-8"
    done
fi
unset _a _v _l _n
