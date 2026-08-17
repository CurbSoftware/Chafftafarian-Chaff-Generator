"""Pack-level template selection: pick templates for planned files.

Selection is weighted by the profile's content domains when template
metadata declares one (via the ``domains`` key in the YAML description
block); otherwise templates of a kind are chosen uniformly.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaff_generator.templates.models import TemplateDef, TemplateRegistry


def pick_template(
    rng: random.Random,
    registry: TemplateRegistry,
    kind: str,
    domains: dict[str, int] | None = None,
) -> TemplateDef | None:
    """Pick a template of ``kind``, weighted by content domains."""
    candidates = registry.for_kind(kind)
    if not candidates:
        return None
    if not domains:
        return candidates[rng.randrange(len(candidates))]

    weights: list[float] = []
    for template in candidates:
        declared = _template_domains(template)
        weight = 1.0
        for domain, domain_weight in domains.items():
            if domain in declared:
                weight = max(weight, float(domain_weight))
        weights.append(weight)
    total = sum(weights)
    threshold = rng.random() * total
    cumulative = 0.0
    for template, weight in zip(candidates, weights, strict=True):
        cumulative += weight
        if cumulative >= threshold:
            return template
    return candidates[-1]


def _template_domains(template: TemplateDef) -> set[str]:
    """Domains declared by a template in its YAML metadata."""
    return set(template.domains)
