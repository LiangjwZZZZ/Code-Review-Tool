from review.engine.impact_analyzer import _parse_gitnexus_output, ImpactItem


GITNEXUS_SAMPLE = """
risk: HIGH
summary: 2 direct callers, 1 affected process

src/auth/session.py:42  SessionManager.validate
src/api/routes.py:18    login

Affected execution flow: UserLogin (step 3)
"""


def test_parse_gitnexus_output_high():
    item = _parse_gitnexus_output("validateToken", GITNEXUS_SAMPLE, "src/auth/token.py")
    assert isinstance(item, ImpactItem)
    assert item.symbol == "validateToken"
    assert item.risk == "HIGH"
    assert len(item.affected_symbols) > 0


def test_parse_gitnexus_output_low_risk():
    output = "risk: LOW\nNo callers found."
    item = _parse_gitnexus_output("_helper", output, "src/utils.py")
    assert item.risk == "LOW"


def test_parse_risk_missing():
    from review.engine.impact_analyzer import _parse_risk
    assert _parse_risk("unknown") == "MEDIUM"
    assert _parse_risk("critical") == "CRITICAL"
    assert _parse_risk("HIGH") == "HIGH"


def test_analyze_symbol_nonexistent():
    """analyze_symbol returns None for symbols not in gitnexus index."""
    from review.engine.impact_analyzer import analyze_symbol
    # Symbol 'nonexistent_symbol_xyz123' won't be indexed — expect None
    result = analyze_symbol("nonexistent_symbol_xyz123")
    assert result is None
