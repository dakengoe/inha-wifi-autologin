#!/bin/bash
# Log out of the Inha Wi-Fi portal.
# Stops the auto-login service first (otherwise it would log you straight back in),
# then calls the portal's logout URL, which is the saved keepalive URL with
# "keepalive" replaced by "logout".
KEEP="$HOME/.inha_keep"

systemctl --user stop inha-wifi.service

if [ ! -s "$KEEP" ]; then
    echo "No saved session token ($KEEP). Start the service, wait for 'logged in', then try again."
    exit 1
fi

URL=$(sed 's/keepalive/logout/' "$KEEP")
curl -sk "$URL" -o /dev/null -w "logout request: HTTP %{http_code}\n"
rm -f "$KEEP"
