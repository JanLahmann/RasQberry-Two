#!/bin/sh
# shellcheck disable=SC2046
source $HOME/RQB2-initial.env
export $(grep -v "^#" "$HOME/$REPO/$ENV" | xargs -d "\n")
