def redemption_state(
    event_status: str,
    coupon_status: str,
    correct_scope: bool,
    serves_option: bool,
    member_active: bool,
) -> str:
    if not correct_scope or not member_active:
        return "INVALID"
    if event_status == "CLOSED" or coupon_status == "EXPIRED":
        return "EXPIRED"
    if coupon_status == "VOID":
        return "CANCELLED"
    if coupon_status == "REDEEMED":
        return "ALREADY_USED"
    if event_status != "LIVE" or coupon_status != "ISSUED":
        return "INVALID"
    if not serves_option:
        return "WRONG_COUNTER"
    return "SERVE"
