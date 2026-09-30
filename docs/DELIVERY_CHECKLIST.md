# Competition Delivery Checklist

## Source and application

- [ ] Source code (`app/`, `scripts/`, `frontend/`) included.
- [ ] `README.md`, `requirements.txt`, `frontend/package.json` and lockfile included.
- [ ] `data/raw/` competition materials remain read-only and are described, not copied into generated docs.
- [ ] No `.env` or API Key is included.

## Demo package

- [ ] `scripts/start_demo.ps1` starts the cached/demo mode.
- [ ] `scripts/demo_preflight.py` reports readiness without printing secrets.
- [ ] `scripts/reset_demo.py` restores risk tracking state without changing source data.
- [ ] `docs/DEMO_SCENARIOS.md` and `docs/DEMO_SCRIPT.md` are included.
- [ ] `docs/DEMO_METRICS.md` clearly labels live N=3 as preliminary.
- [ ] `/workbench` and `/risk-dashboard` form the verified interaction loop.

## Presentation assets to provide separately

- [ ] Demo video recording.
- [ ] Competition PPT/slides.
- [ ] Agent design and evaluation explanation.
- [ ] Environment setup instructions and known limitations.

Real Qianniu production integration is an optional M11 enhancement and is not required for this package.
