# RasQberry QuBins: a start hook of the Jupyter Docker Stacks image
# (/usr/local/bin/before-notebook.d, sourced by start.sh). The image has an
# empty "work" folder in /home/jovyan, which showed next to my-work in the
# lab: remove it when it is empty. Nothing else is changed.
rmdir /home/jovyan/work 2>/dev/null || true
