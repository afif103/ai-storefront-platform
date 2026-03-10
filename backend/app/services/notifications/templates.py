"""Plain text notification message templates."""


def format_order_notification(
    tenant_name: str,
    order_number: str,
    total: str,
    currency: str,
    customer_name: str,
) -> tuple[str, str]:
    """Return (subject, body) for an order notification."""
    subject = f"[{tenant_name}] New order {order_number}"
    body = (
        f"New order received\n"
        f"\n"
        f"Order: {order_number}\n"
        f"Customer: {customer_name}\n"
        f"Total: {total} {currency}\n"
    )
    return subject, body


def format_donation_notification(
    tenant_name: str,
    donation_number: str,
    amount: str,
    currency: str,
    donor_name: str,
) -> tuple[str, str]:
    """Return (subject, body) for a donation notification."""
    subject = f"[{tenant_name}] New donation {donation_number}"
    body = (
        f"New donation received\n"
        f"\n"
        f"Donation: {donation_number}\n"
        f"Donor: {donor_name}\n"
        f"Amount: {amount} {currency}\n"
    )
    return subject, body
