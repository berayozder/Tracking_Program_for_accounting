"""
VAT/KDV calculation utility.
"""
def compute_vat(amount, vat_rate, is_inclusive):
    """
    Compute net and VAT amount from a total or net value.
    Args:
        amount (float): The amount (either net or gross).
        vat_rate (float): VAT rate as a percentage (e.g., 18 for 18%).
        is_inclusive (bool): If True, amount includes VAT; if False, amount is net (VAT will be added).
    Returns:
        tuple: (net_amount, vat_amount)
    """
    if vat_rate is None:
        vat_rate = 0.0
    rate = float(vat_rate) / 100.0
    if is_inclusive:
        net = float(amount) / (1 + rate) if rate else float(amount)
        vat = float(amount) - net
    else:
        net = float(amount)
        vat = net * rate
    return round(net, 2), round(vat, 2)
