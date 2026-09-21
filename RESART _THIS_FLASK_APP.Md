systemctl --user restart flask-interns.service   # restart after code changes
systemctl --user status flask-interns.service    # check state
journalctl --user -u flask-interns.service -f