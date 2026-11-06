ui_print "- Enabling vivo HDR UI in the shared feature configuration"

mkdir -p "$MODPATH/system/vendor/etc"
awk '
  /^\[/ {
    xdr = ($0 == "[vivo.hardware.display.xdr]")
    found = found || xdr
  }
  xdr && /^[[:space:]]*hdrui[[:space:]]*=/ { next }
  xdr && /^[[:space:]]*is_support_zygote[[:space:]]*=/ { next }
  { print }
  xdr && /^\[/ {
    print "hdrui=true"
    print "is_support_zygote=1"
  }
  END { if (!found) exit 1 }
' /vendor/etc/vivo_config.ini > "$MODPATH/system/vendor/etc/vivo_config.ini" \
  || abort "! Required vivo HDR configuration or section was not found"

set_perm_recursive "$MODPATH/system" 0 0 0755 0644 u:object_r:vendor_file:s0
set_perm "$MODPATH/system/vendor/etc/vivo_config.ini" 0 0 0644 u:object_r:vendor_configs_file:s0

ui_print "- Soft reboot once to mount the configuration and refresh ConfigStore"
