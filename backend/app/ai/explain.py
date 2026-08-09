"""Templated explanation — prose is derived strictly from the factor list."""

from __future__ import annotations

from app.schemas.models import Factor, SignalAction

_STANDARD_PREFIXES = (
    "AI Confidence:",
    "Action:",
    "Reason:",
    "Unavailable (confidence reduced; not treated as neutral):",
    "These are probabilistic forecasts based on observed data, not certainties.",
)


def explain(
    action: SignalAction,
    confidence: float,
    factors: list[Factor],
    missing: list[str],
) -> list[str]:
    lines = [
        f"AI Confidence: {confidence:.0f}% (probabilistic forecast — not a guarantee)",
        f"Action: {action}",
        "Reason:",
    ]
    ranked = sorted(factors, key=lambda f: abs(f.contribution), reverse=True)
    for f in ranked:
        sign = "+" if f.contribution >= 0 else ""
        lines.append(
            f"  • {f.name}: {f.observed} ({f.direction}, contrib {sign}{f.contribution:.2f}, source={f.source})"
        )
    if missing:
        lines.append("Unavailable (confidence reduced; not treated as neutral):")
        for m in missing:
            lines.append(f"  • {m}")
    lines.append(
        "These are probabilistic forecasts based on observed data, not certainties."
    )
    return lines


def validate_explanation(
    reasoning: list[str],
    factors: list[Factor],
    missing: list[str],
) -> None:
    """Raise AssertionError when reasoning drifts from factors/missing lists."""
    factor_names = {f.name for f in factors}
    missing_set = set(missing)
    text = "\n".join(reasoning)
    in_unavailable = False

    for name in factor_names:
        if name not in text:
            raise AssertionError(f"Explanation missing factor: {name}")

    for item in missing:
        if item not in text:
            raise AssertionError(f"Explanation missing unavailable factor: {item}")

    for line in reasoning:
        stripped = line.strip()
        if stripped.startswith("Unavailable"):
            in_unavailable = True
            continue
        if stripped.startswith("These are probabilistic"):
            in_unavailable = False
            continue
        if any(
            stripped.startswith(prefix)
            for prefix in _STANDARD_PREFIXES
            if prefix != "Unavailable (confidence reduced; not treated as neutral):"
        ):
            in_unavailable = False
            continue
        if line.startswith("  • "):
            body = line[4:]
            if in_unavailable:
                entry = body.split(":", 1)[0].strip()
                if entry not in missing_set:
                    raise AssertionError(f"Unexpected unavailable entry: {entry}")
            else:
                matched = next(
                    (fname for fname in sorted(factor_names, key=len, reverse=True) if body.startswith(f"{fname}:")),
                    None,
                )
                if matched is None:
                    raise AssertionError(f"Explanation mentions non-factor bullet: {body.split(':', 1)[0]}")
            continue
        if not stripped:
            continue
        raise AssertionError(f"Non-templated explanation line: {line}")

    if "probabilistic" not in text.lower():
        raise AssertionError("Explanation missing probabilistic disclaimer language")
