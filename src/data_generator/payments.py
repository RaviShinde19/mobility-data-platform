"""
payments.py — Payment Data Generator
═════════════════════════════════════

WHAT THIS DOES:
───────────────
Generates payment records linked to rides.

KEY DESIGN DECISIONS:
─────────────────────
1. NOT every ride gets a payment:
   - completed rides → always have a payment
   - cancelled rides → 30% had a payment (cancellation fee)
   - ongoing rides → no payment yet
   - no_show rides → 50% had a cancellation charge

2. Payment amount ≈ ride fare (but not always exact)
   - Some payments include tips
   - Failed payments might have a different amount (partial charges)

3. Payment time is AFTER ride completion
   This mimics real payment processing — there's always a delay
   between ride completion and payment settlement.

SYSTEM DESIGN NOTE — Payment Processing:
─────────────────────────────────────────
Real payment systems are one of the most complex parts of any platform:

  SCALE 1 (Current) — Single payment table
    Ride completes → one payment record

  SCALE 2 — Payment gateway integration
    Ride completes → payment intent → authorization → capture → settlement
    Each step is a separate event (5+ records per payment)

  SCALE 3 — Distributed payment processing
    Payment Service → Gateway → Bank Network → Settlement
    Idempotency keys prevent double-charging
    Saga pattern for multi-step transactions
    Event sourcing for complete audit trail

For our analytics platform, we care about the FINAL state of each
payment — did it succeed, fail, or get refunded?
"""

import random
from datetime import timedelta
from dataclasses import asdict

from src.models.schemas import Payment
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def generate_payments(
    num_payments: int,
    rides: list[dict],
    payment_params: dict,
    seed: int = 42
) -> list[dict]:
    """
    Generate payment records linked to rides.

    Args:
        num_payments: Target number of payments to generate.
        rides: List of ride dicts (we reference their IDs and fares).
        payment_params: Payment config (methods, statuses, weights).
        seed: Random seed.

    Returns:
        List of payment dicts.

    NOTE: The actual number of payments may be <= num_payments
    because we only generate payments for eligible rides.
    """
    random.seed(seed + 300)

    methods = [m["method"] for m in payment_params["methods"]]
    method_weights = [m["weight"] for m in payment_params["methods"]]
    statuses = [s["status"] for s in payment_params["statuses"]]
    status_weights = [s["weight"] for s in payment_params["statuses"]]

    # Determine which rides are eligible for payment
    eligible_rides = []
    for ride in rides:
        status = ride["ride_status"]
        if status == "completed":
            eligible_rides.append(ride)
        elif status == "cancelled" and random.random() < 0.30:
            eligible_rides.append(ride)
        elif status == "no_show" and random.random() < 0.50:
            eligible_rides.append(ride)
        # ongoing rides: no payment yet

    # Shuffle and take up to num_payments
    random.shuffle(eligible_rides)
    eligible_rides = eligible_rides[:num_payments]

    payments = []

    logger.info(
        f"Starting payment generation: target={num_payments}, "
        f"eligible rides={len(eligible_rides)}"
    )

    for i, ride in enumerate(eligible_rides, 1):
        # Payment method (weighted)
        payment_method = random.choices(methods, weights=method_weights, k=1)[0]

        # Payment status (weighted — most complete, some fail)
        payment_status = random.choices(statuses, weights=status_weights, k=1)[0]

        # Amount based on ride fare
        base_amount = ride["fare"]

        # For cancelled/no_show, charge a partial cancellation fee
        if ride["ride_status"] in ("cancelled", "no_show"):
            base_amount = round(base_amount * random.uniform(0.1, 0.3), 2)

        # Tip: 20% of completed rides get a tip
        tip_amount = 0.0
        if ride["ride_status"] == "completed" and random.random() < 0.20:
            tip_amount = round(random.uniform(10, 100), 2)

        # Failed payments might have 0 amount
        if payment_status == "failed":
            base_amount = 0.0
            tip_amount = 0.0

        # Payment time: after ride completion (1-30 minutes delay)
        reference_time = (
            ride.get("dropoff_time")
            or ride.get("pickup_time")
            or ride["request_time"]
        )

        # Handle both string and datetime reference_time
        if isinstance(reference_time, str):
            from datetime import datetime
            try:
                reference_time = datetime.fromisoformat(reference_time)
            except ValueError:
                reference_time = datetime.strptime(reference_time, "%Y-%m-%d %H:%M:%S")

        payment_time = reference_time + timedelta(minutes=random.randint(1, 30))

        payment = Payment(
            payment_id=f"P{i:05d}",
            ride_id=ride["ride_id"],
            customer_id=ride["customer_id"],
            amount=base_amount,
            payment_method=payment_method,
            payment_status=payment_status,
            payment_time=payment_time,
            tip_amount=tip_amount
        )

        payments.append(asdict(payment))

    # ─── Log summary ─────────────────────────────────────────
    method_dist = {}
    status_dist = {}
    for p in payments:
        m = p["payment_method"]
        s = p["payment_status"]
        method_dist[m] = method_dist.get(m, 0) + 1
        status_dist[s] = status_dist.get(s, 0) + 1

    total_revenue = sum(p["amount"] for p in payments)
    total_tips = sum(p["tip_amount"] for p in payments)

    logger.info(
        f"Payment generation complete: {len(payments)} records | "
        f"Total revenue: ₹{total_revenue:,.2f} | "
        f"Total tips: ₹{total_tips:,.2f}"
    )
    logger.info(f"Payment methods: {method_dist}")
    logger.info(f"Payment statuses: {status_dist}")

    return payments
