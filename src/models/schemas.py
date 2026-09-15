"""
schemas.py — Data Schemas & Field Definitions
══════════════════════════════════════════════

WHY THIS EXISTS:
────────────────
A schema defines the SHAPE of your data:
  - What columns exist?
  - What are their types?
  - What are valid values?

Without schemas, your pipeline is fragile:
  - Column "fare" could be a string in one file, float in another
  - A misspelled column name silently creates bad data
  - No way to validate incoming data against expectations

DESIGN DECISION — Dataclasses over Dicts:
─────────────────────────────────────────
We use Python dataclasses here because:
  1. Self-documenting — the class IS the documentation
  2. Type hints — your IDE catches errors before runtime
  3. Validation-ready — easy to add validators later
  4. Immutable option — frozen=True prevents accidental mutation

In later phases, these schemas will map directly to:
  - PostgreSQL table definitions (Phase 2)
  - PySpark StructTypes (Phase 4)
  - Glue table schemas (Phase 7)
  - Redshift DDL (Phase 9)

SYSTEM DESIGN NOTE:
───────────────────
Schema management is a CRITICAL system design topic:

  SCALE 1 (Current) — Schemas defined in code
    Pro: Simple, version-controlled
    Con: Schema changes require code deployment

  SCALE 2 — Schema Registry (e.g., AWS Glue Data Catalog)
    Schemas stored centrally, versioned independently
    Producers and consumers agree on schema before exchanging data

  SCALE 3 — Schema Evolution with compatibility rules
    Backward/forward compatible changes
    Avro, Protobuf, or Delta Lake schema enforcement
    Critical for real-time streaming (V2 Kafka)
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


@dataclass
class Customer:
    """
    Represents a registered platform customer.

    In a real system, this comes from the user registration service.
    """
    customer_id: str = field(metadata={"classification": "INTERNAL"})           # e.g., "C0001" — unique identifier
    first_name: str = field(metadata={"classification": "CONFIDENTIAL"})
    last_name: str = field(metadata={"classification": "CONFIDENTIAL"})
    email: str = field(metadata={"classification": "CONFIDENTIAL"})
    phone: str = field(metadata={"classification": "CONFIDENTIAL"})
    city: str = field(metadata={"classification": "PUBLIC"})                  # Registration city
    signup_date: date = field(metadata={"classification": "PUBLIC"})
    is_active: bool = field(default=True, metadata={"classification": "PUBLIC"})

    # Columns list for CSV header
    @classmethod
    def columns(cls) -> list[str]:
        return [
            "customer_id", "first_name", "last_name", "email",
            "phone", "city", "signup_date", "is_active"
        ]


@dataclass
class Driver:
    """
    Represents a registered driver on the platform.

    In a real system, this comes from the driver onboarding service.
    """
    driver_id: str = field(metadata={"classification": "INTERNAL"})             # e.g., "D0001"
    first_name: str = field(metadata={"classification": "CONFIDENTIAL"})
    last_name: str = field(metadata={"classification": "CONFIDENTIAL"})
    phone: str = field(metadata={"classification": "CONFIDENTIAL"})
    city: str = field(metadata={"classification": "PUBLIC"})
    vehicle_type: str = field(metadata={"classification": "PUBLIC"})          # Sedan, Hatchback, SUV, Auto, Bike
    license_number: str = field(metadata={"classification": "CONFIDENTIAL"})
    rating: float = field(metadata={"classification": "PUBLIC"})              # 3.0 to 5.0
    join_date: date = field(metadata={"classification": "PUBLIC"})
    is_active: bool = field(default=True, metadata={"classification": "PUBLIC"})

    @classmethod
    def columns(cls) -> list[str]:
        return [
            "driver_id", "first_name", "last_name", "phone",
            "city", "vehicle_type", "license_number", "rating",
            "join_date", "is_active"
        ]


@dataclass
class Ride:
    """
    Represents a single ride/trip on the platform.

    This is the CORE transactional entity — every ride links
    a customer to a driver at a specific time and place.

    In a real system, ride events stream from the dispatch service.
    """
    ride_id: str = field(metadata={"classification": "INTERNAL"})               # e.g., "R00001"
    customer_id: str = field(metadata={"classification": "INTERNAL"})           # FK → Customer
    driver_id: str = field(metadata={"classification": "INTERNAL"})             # FK → Driver
    pickup_city: str = field(metadata={"classification": "PUBLIC"})
    pickup_area: str = field(metadata={"classification": "PUBLIC"})
    dropoff_city: str = field(metadata={"classification": "PUBLIC"})
    dropoff_area: str = field(metadata={"classification": "PUBLIC"})
    pickup_lat: float = field(metadata={"classification": "RESTRICTED"})
    pickup_lon: float = field(metadata={"classification": "RESTRICTED"})
    dropoff_lat: float = field(metadata={"classification": "RESTRICTED"})
    dropoff_lon: float = field(metadata={"classification": "RESTRICTED"})
    request_time: datetime = field(metadata={"classification": "PUBLIC"})
    distance_km: float = field(metadata={"classification": "PUBLIC"})
    fare: float = field(metadata={"classification": "PUBLIC"})
    surge_multiplier: float = field(metadata={"classification": "PUBLIC"})
    ride_status: str = field(metadata={"classification": "PUBLIC"})           # completed | cancelled | ongoing | no_show
    pickup_time: Optional[datetime] = field(default=None, metadata={"classification": "PUBLIC"})    # NULL if cancelled before pickup
    dropoff_time: Optional[datetime] = field(default=None, metadata={"classification": "PUBLIC"})   # NULL if not completed

    @classmethod
    def columns(cls) -> list[str]:
        return [
            "ride_id", "customer_id", "driver_id",
            "pickup_city", "pickup_area", "dropoff_city", "dropoff_area",
            "pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon",
            "request_time", "pickup_time", "dropoff_time",
            "distance_km", "fare", "surge_multiplier", "ride_status"
        ]


@dataclass
class Payment:
    """
    Represents a payment transaction for a ride.

    In a real system, this comes from the payment gateway service.
    Note: Not every ride has a payment (cancelled rides may not).
    """
    payment_id: str = field(metadata={"classification": "INTERNAL"})            # e.g., "P00001"
    ride_id: str = field(metadata={"classification": "INTERNAL"})               # FK → Ride
    customer_id: str = field(metadata={"classification": "INTERNAL"})           # FK → Customer
    amount: float = field(metadata={"classification": "PUBLIC"})
    payment_method: str = field(metadata={"classification": "PUBLIC"})        # UPI | Credit Card | Debit Card | Cash | Wallet
    payment_status: str = field(metadata={"classification": "PUBLIC"})        # completed | failed | refunded | pending
    payment_time: datetime = field(metadata={"classification": "PUBLIC"})
    tip_amount: float = field(default=0.0, metadata={"classification": "PUBLIC"})

    @classmethod
    def columns(cls) -> list[str]:
        return [
            "payment_id", "ride_id", "customer_id",
            "amount", "payment_method", "payment_status",
            "payment_time", "tip_amount"
        ]


# ─── Valid values for validation ────────────────────────────
VALID_RIDE_STATUSES = {"completed", "cancelled", "ongoing", "no_show"}
VALID_PAYMENT_METHODS = {"UPI", "Credit Card", "Debit Card", "Cash", "Wallet"}
VALID_PAYMENT_STATUSES = {"completed", "failed", "refunded", "pending"}
VALID_VEHICLE_TYPES = {"Sedan", "Hatchback", "SUV", "Auto", "Bike"}
