# milos-timotijevic.github.io
Academic profile and bibliography of Miloš Timotijević

## Local validation

The repository uses standard-library Python checks so that the public site can
be validated locally before a pull request is opened:

```text
python scripts/validate_site.py .
python scripts/audit_accessibility.py .
python scripts/audit_maintainability.py .
```

The maintainability audit reports the largest HTML pages and the amount of
inline CSS, and rejects accidental page or style bloat. It is an inventory and
regression guard; it does not rewrite scholarly content or change the site's
visual design.
