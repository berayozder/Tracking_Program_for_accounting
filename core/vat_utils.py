"""VAT/KDV calculation utility."""
from __future__ import annotations


def compute_vat(
    amount: float, vat_rate: float | None, is_inclusive: bool
) -> tuple[float, float]:
    """
    Compute net and VAT amount from a total or net value.

    Args:
        amount: The amount (either net or gross).
        vat_rate: VAT rate as a percentage (e.g., 18 for 18%). None defaults to 0.
        is_inclusive: If True, amount includes VAT; if False, amount is net.

    Returns:
        Tuple of (net_amount, vat_amount)
    """
    rate = float(vat_rate or 0.0) / 100.0
    if is_inclusive:
        net = float(amount) / (1 + rate)
        vat = float(amount) - net
    else:
        net = float(amount)
        vat = net * rate
    return round(net, 2), round(vat, 2)
