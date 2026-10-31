# inha-wifi-autologin

Automatic login for the Inha University in Tashkent Wi-Fi captive portal on Linux.
It logs you in as soon as you join the network, keeps the session alive, and gives you a one-command logout.

Tested on Ubuntu with the portal at `gwd.inha.uz:1003` (a FortiGate firewall).
It uses **your own** credentials and only automates the form you would otherwise fill in the browser. It does not bypass any authentication.

## How it works

The portal does not send a normal HTTP redirect. Opening any plain-HTTP page returns a
small page with a JavaScript redirect to `https://gwd.inha.uz:1003/fgtauth?<magic>`. The
script:

1. requests `http://neverssl.com` and looks for that redirect (no redirect = already online),
2. opens the login page and copies its hidden form fields (`magic`, `4Tredir`),
3. POSTs them with your user ID and password, sending the same `Referer`/`Origin` headers a
   browser would (without them the portal answers "Firewall authentication failed"),
4. takes the `keepalive` URL from the response and pings it every 2 minutes,
5. saves that URL to `~/.inha_keep`. Logging out is the same URL with `keepalive` replaced
   by `logout`.

The portal name only resolves while you are logged out, so the script resolves the IP at
login time and uses it for the keepalive pings.

## Requirements

- Linux with systemd (user services), Python 3 and the `requests` package

```bash
sudo apt install python3-requests
```

## Setup

```bash
# 1. get the files
git clone https://github.com/dakengoe/inha-wifi-autologin.git ~/inha-wifi-autologin
cd ~/inha-wifi-autologin

# 2. credentials: line 1 = user ID, line 2 = password, nothing else
nano ~/.inha_cred
chmod 600 ~/.inha_cred

# 3. install and start the background service
mkdir -p ~/.config/systemd/user
cp inha-wifi.service.example ~/.config/systemd/user/inha-wifi.service
systemctl --user daemon-reload
systemctl --user enable --now inha-wifi.service

# 4. optional: short logout command
chmod +x wifi-logout.sh
echo "alias wifi-logout='$HOME/inha-wifi-autologin/wifi-logout.sh'" >> ~/.bashrc
source ~/.bashrc
```

If `requests` is installed in a different Python (conda, venv), put the full path to that
Python in the `ExecStart` line of the service file.

## Usage

| Task | Command |
|------|---------|
| Is it running? | `systemctl --user status inha-wifi.service` |
| Live log | `journalctl --user -u inha-wifi -f` |
| Log out (stops the service first) | `wifi-logout` |
| Log back in | `systemctl --user start inha-wifi.service` |
| Stop now (starts again at next login) | `systemctl --user stop inha-wifi.service` |
| Turn off auto-start | `systemctl --user disable --now inha-wifi.service` |
| Restart after editing the script or credentials | `systemctl --user restart inha-wifi.service` |

After a connection, login happens within one check interval (2 minutes by default;
change `CHECK_INTERVAL` in `auto_login.py`).

`wifi-logout` stops the service before logging out, because otherwise the script would log
you straight back in. After a reboot the service starts again and logs you in.

## Files

| File | Purpose |
|------|---------|
| `auto_login.py` | The login and keepalive loop |
| `wifi-logout.sh` | Stops the service and calls the portal's logout URL |
| `inha-wifi.service.example` | systemd user service |
| `credentials.example` | Format of `~/.inha_cred` |

## Security notes

- Credentials live in `~/.inha_cred` (keep it `chmod 600`) and are never part of the repo.
  Do not commit that file, and do not put the password in the script.
- `~/.inha_keep` holds a session token. It stops working after you log out.
- The portal certificate does not match the address the script connects to, so TLS
  verification is disabled for requests to the portal. The script only sends your
  credentials to `https://gwd.inha.uz:1003` and ignores captive portals of other networks.
- Wrong credentials: the script waits 5 minutes between failed attempts to avoid locking
  the account.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Log says `login failed` | Check `~/.inha_cred` (no extra spaces or empty lines), then restart the service |
| `Failed to resolve gwd.inha.uz` in a keepalive error | Normal while logged in; the script already uses the IP for keepalive |
| `wifi-logout` says no saved token | Start the service, wait for `logged in` in the log, try again |
| Service fails to start | `journalctl --user -u inha-wifi -n 30`; usually a wrong Python path in the service file |
| Browser shows `ERR_EMPTY_RESPONSE` on the portal address | Normal: the portal ignores requests without a valid token |

## Disclaimer

Intended for personal use with your own account. Check the university's IT rules if in
doubt. Other FortiGate captive portals may work after changing `PORTAL_HOST` and
`PORTAL_PORT`, but this has only been tested on the Inha network.
