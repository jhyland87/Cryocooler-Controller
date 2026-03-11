#!/usr/bin/env bash

fileprefix="fsm_block_"

cd $(git rev-parse --show-toplevel)

awk -v prefix="${fileprefix}" '/^```mermaid/ {f=1; k++; out=prefix k ".mmd"; next} /^```$/ && f {f=0; close(out); next} f {print > out}' state_machine.md

ls -1 ${fileprefix}*.mmd | while read -r diagram; do
    mmdc -i "$diagram" -o "${diagram%.mmd}.pdf"
		magick -density 300 "${diagram%.mmd}.pdf" -quality 100 "${diagram%.mmd}.png"
		rm "${diagram%.mmd}.pdf"
    echo "Generated ${diagram%.mmd}.png"
		open ${diagram%.mmd}.png
done
