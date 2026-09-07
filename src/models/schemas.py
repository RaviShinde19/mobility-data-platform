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
    customer_id: str           # e.g., "C0001" — unique identifier
    first_name: str
    last_name: str
    email: str
    phone: str
    city: str                  # Registration city
    signup_date: date
    is_active: bool = True

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
    driver_id: str             # e.g., "D0001"
    first_name: str
    last_name: str
    phone: str
    city: str
    vehicle_type: str          # Sedan, Hatchback, SUV, Auto, Bike
    license_number: str
    rating: float              # 3.0 to 5.0
    join_date: date
    is_active: bool = True

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
    ride_id: str               # e.g., "R00001"
    customer_id: str           # FK → Customer
    driver_id: str             # FK → Driver
    pickup_city: str
    pickup_area: str
    dropoff_city: str
    dropoff_area: str
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    request_time: datetime
    pickup_time: Optional[datetime]    # NULL if cancelled before pickup
    dropoff_time: Optional[datetime]   # NULL if not completed
    distance_km: float
    fare: float
    surge_multiplier: float
    ride_status: str           # completed | cancelled | ongoing | no_show

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
    payment_id: str            # e.g., "P00001"
    ride_id: str               # FK → Ride
    customer_id: str           # FK → Customer
    amount: float
    payment_method: str        # UPI | Credit Card | Debit Card | Cash | Wallet
    payment_status: str        # completed | failed | refunded | pending
    payment_time: datetime
    tip_amount: float = 0.0

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
