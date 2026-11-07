#!/system/bin/sh

MODDIR=${0%/*}
umask 077
workdir=$(mktemp -d "$MODDIR/.bugreport.XXXXXX") || exit 1
trap 'rm -rf "$workdir"' EXIT
report="/sdcard/Download/OriginHDRFix_bugreport_$(date +%Y-%m-%d_%H_%M_%S).tar.gz"
mkdir -p "$workdir/files" "$(dirname "$report")" || exit 1

printf '%s\n' '- Collecting OriginHDRFix diagnostics'
dumpsys display > "$workdir/files/display.txt" 2>&1
dumpsys SurfaceFlinger --display-id > "$workdir/files/surfaceflinger.txt" 2>&1
dumpsys SurfaceFlinger --list > "$workdir/files/surfaceflinger-layers.txt" 2>&1

collect_file() {
  [ -f "$1" ] || return 0
  mkdir -p "$workdir/files/$(dirname "$2")" || exit 1
  cp "$1" "$workdir/files/$2" || exit 1
}

for file in \
  /vendor/etc/vivo_config.ini \
  /vendor/etc/displayconfig/*.xml \
  /sys/lcm/panel_name \
  /sys/lcm/panel_info \
  /sys/lcm/error_info \
  /sys/lcm/bl_level \
  /system/etc/LcmConfig/LcmBrightnessConfig.json \
  /system/etc/LcmConfig/LcmMapNit.json \
  /system/etc/LcmConfig/XdrBrightnessConfig.json \
  /system/framework/vivo-framework.jar \
  /system/framework/vivo-services.jar; do
  collect_file "$file" "${file#/}"
done

for file in \
  system.prop \
  system/vendor/etc/vivo_config.ini \
  system/etc/LcmConfig/LcmBrightnessConfig.json; do
  collect_file "$MODDIR/$file" "module/$file"
done

tar -czf "$workdir/report.tar.gz" -C "$workdir/files" . || exit 1
cp "$workdir/report.tar.gz" "$report" || exit 1
chmod 0644 "$report" || exit 1
printf '\nSaved to: %s\n' "$report"
printf '%s\n' 'Submit this archive together with the KernelSU bugreport.'
