# Contributing and testing

This is an **experimental beta**, seeking reproducible feedback. Most helpful contributions are narrowly scoped: a failing synthetic Git fixture, confusing report, legitimate false positive, or safe improvement to installation.

Before opening an issue, please check existing reports. Never include production secrets, private repository names, proprietary code, or exploit details in public Issues.

## Reproducing failures

Use Python 3.11+ and Git, from a trusted checkout:

~~~sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
~~~

Each regression test must use a disposable Git repository. For a bug, please describe expected versus actual results and provide a minimal **synthetic** reproduction that does not depend on private infrastructure.

## Expectations

- Keep the project's scope narrow; avoid inventing a new policy framework or undocumented enforcement claims.
- Fail conservatively on invalid Git states and policy inputs.
- Read policy only from an independently approved baseline, not the coding agent's candidate.
- Keep false positives and setup burden as important as detection coverage.
- Preserve the distinctions between post-change scope, optional test checks and task completion.
- Do not submit raw external-checker stdout/stderr containing personal or sensitive information.

## Security problems

Follow [SECURITY.md](SECURITY.md); do not post exploit details publicly.

## Project status

The maintainers may not accept every contribution, guarantee response times, or develop a paid version. Participation is voluntary. Contributions should be made as issues or pull requests in this public distribution repository, never by requesting access to private Velorin research repositories.
