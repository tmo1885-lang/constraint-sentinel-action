# Contributing (historical research repository)

**Development paused; beta recruitment closed (November 2026).** Constraint Sentinel is preserved as a public experimental research record, not an actively maintained product or volunteer testing program. We are **not asking for new beta trials, feature proposals, or adoption reports**. Existing work and negative findings remain available for reproducibility. No issue response, fix, or PR review turnaround is guaranteed.

Before opening an issue, please check existing reports. Never include production secrets, private repository names, proprietary code, or exploit details in public Issues.

## Reproducing historical failures

If independently examining the published research, use Python 3.11+ and Git, from a trusted checkout in a disposable environment:

~~~sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
~~~

Each regression test must use a disposable Git repository. Historical inaccuracies can be reported with a minimal **synthetic** reproduction that does not depend on private infrastructure; please do not interpret this as an invitation to join an ongoing beta.

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

The maintainers have paused active development and are not recruiting volunteers. Factual corrections to the public research record may be considered without any promise of review or implementation. Do not request access to private Velorin research repositories. For security-sensitive reports, follow [SECURITY.md](SECURITY.md).
