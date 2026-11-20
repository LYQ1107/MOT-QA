#!/bin/sh
set -eu
recovery_dir=/data3/liuyeqiang/TOC_Bench_recovery_20261120
archive=/data3/liuyeqiang/nas/A800/motqa_pilot_migration_20261113/motqa_pilot_code_results.tar
mount_dir="$recovery_dir/motqa_nas_archive"
if mountpoint -q "$mount_dir"; then
    exit 0
fi
test -r "$archive"
mkdir -p "$mount_dir"
exec "$recovery_dir/.venv/bin/ratarmount" --no-recreate-index -o ro \
    --index-file "$recovery_dir/motqa_archive.remote-index.sqlite" \
    --log-file "$recovery_dir/ratarmount.log" "$archive" "$mount_dir"
