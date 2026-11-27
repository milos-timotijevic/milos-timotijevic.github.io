# milos-timotijevic.github.io
Academic profile and bibliography of Miloš Timotijević

## Published research data

The fixed academic data release 1.0 was published on 27 November 2026 in Harvard Dataverse: [DOI 10.7910/DVN/LYPAQH](https://doi.org/10.7910/DVN/LYPAQH), [Wikidata Q142312195](https://www.wikidata.org/wiki/Q142312195). It contains 108 bibliographic records, 1,454 qualified relation statements and 143 publication-to-cluster links across seven clusters. The deposit is distinct from this evolving website. Use the repository ZIP for reproducible analysis of that release. Original data: CC BY 4.0; original code: MIT; third-party terms remain applicable.

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
