#!/usr/bin/env python3
"""Automatic login for the Inha University (Tashkent) Wi-Fi captive portal.

The portal is a FortiGate firewall at gwd.inha.uz:1003. This script:
  1. checks every few minutes whether the portal is asking for a login,
  2. logs in with the credentials from ~/.inha_cred if it is,
  3. otherwise pings the keepalive URL so the session stays open,
  4. saves the current keepalive URL to ~/.inha_keep (used by wifi-logout.sh).

Credentials file (~/.inha_cred): line 1 = user ID, line 2 = password.
"""
import os
import re
import socket
import sys
import time

import requests
import urllib3

PORTAL_HOST = "gwd.inha.uz"
PORTAL_PORT = 1003
BASE = f"https://{PORTAL_HOST}:{PORTAL_PORT}"
CHECK_URL = "http://neverssl.com"      # plain-HTTP page that triggers the portal redirect

CHECK_INTERVAL = 120                   # seconds between checks
RETRY_AFTER_FAILURE = 300              # wait after a failed login (avoids locking the account)

CRED_FILE = os.path.expanduser(os.environ.get("INHA_CRED_FILE", "~/.inha_cred"))
KEEP_FILE = os.path.expanduser("~/.inha_keep")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# The portal certificate does not match the address we connect to, so verification is
# turned off. Credentials are only ever sent to BASE (see login()).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def load_credentials():
    try:
        with open(CRED_FILE) as f:
            lines = f.read().splitlines()
        return lines[0].strip(), lines[1]
    except (OSError, IndexError):
        sys.exit(f"Cannot read credentials from {CRED_FILE}. "
                 "Expected: line 1 = user ID, line 2 = password.")


def portal_url(session):
    """Return the portal login URL if we are logged out, else None.

    The portal answers with a 200 page containing a JavaScript redirect, not an
    HTTP redirect, so the URL has to be pulled out of the body.
    """
    try:
        r = session.get(CHECK_URL, timeout=5)
    except requests.RequestException:
        return None                    # no network at all
    m = re.search(r'window\.location="([^"]+)"', r.text)
    if not m:
        return None                    # already online
    url = m.group(1)
    if not url.startswith(BASE + "/"):
        return None                    # some other network's portal: do not touch it
    return url


def login(session, auth_url, user, password):
    """Log in and return the keepalive URL, or None if the login failed."""
    # The portal name only resolves while we are logged out, so resolve it now
    # and use the IP for later keepalive requests.
    ip = socket.gethostbyname(PORTAL_HOST)

    page = session.get(auth_url, verify=False, timeout=10)
    fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', page.text))
    fields["username"] = user
    fields["password"] = password

    resp = session.post(BASE + "/", data=fields, verify=False, timeout=10,
                        headers={"Referer": auth_url, "Origin": BASE})
    found = re.findall(r'https://[^"\']*keepalive[^"\']*', resp.text)
    return found[0].replace(PORTAL_HOST, ip) if found else None


def save_keepalive(url):
    fd = os.open(KEEP_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(url)


def load_keepalive():
    try:
        with open(KEEP_FILE) as f:
            return f.read().strip() or None
    except OSError:
        return None


def main():
    user, password = load_credentials()
    keep = load_keepalive()

    while True:
        session = requests.Session()
        session.headers.update(HEADERS)
        try:
            auth_url = portal_url(session)
            if auth_url:                               # logged out -> log in
                keep = login(session, auth_url, user, password)
                if keep:
                    save_keepalive(keep)
                    log("logged in")
                else:
                    log("login failed, waiting 5 min")
                    time.sleep(RETRY_AFTER_FAILURE)
                    continue
            elif keep:                                 # online -> keep the session alive
                requests.get(keep, verify=False, timeout=10, headers=HEADERS)
        except requests.RequestException as e:
            log(f"network error: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
