"""Run every check for a site."""
from . import aeo, seo, ux
from .common import Check


def run_all(site, cfg) -> list[Check]:
    if not site.pages:
        return []
    return ux.run(site, cfg) + seo.run(site, cfg) + aeo.run(site, cfg)
