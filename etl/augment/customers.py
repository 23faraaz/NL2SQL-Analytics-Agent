import random

import pandas as pd
from faker import Faker

from etl.augment.config import ACQUISITION_CHANNELS, AUGMENTATION_SEED


CUSTOMER_FINAL_COLUMNS = [
    "customer_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "address_line_1",
    "city",
    "region",
    "postcode",
    "country",
    "acquisition_channel",
]

# SYNTHETIC: generated deterministically by this module, not present in
# any real Olist data. REAL/DERIVED columns (city, region, postcode,
# country) pass through unchanged from the S4a stage.
SYNTHETIC_COLUMNS = [
    "first_name",
    "last_name",
    "email",
    "phone",
    "address_line_1",
    "acquisition_channel",
]


def augment_customers(
    customers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add the customer-identity fields Olist cannot provide (fully
    anonymised source data) to the S4a real/derived customers output.

    Every generated value is SYNTHETIC and deterministic for a given
    ETL_AUGMENTATION_SEED: first_name, last_name, email, phone,
    address_line_1, and acquisition_channel. Real fields already present
    (city, region, postcode, country) are never overwritten.
    """

    required_columns = {"customer_id", "city", "region", "postcode", "country"}
    missing_columns = required_columns - set(customers.columns)

    if missing_columns:
        raise ValueError(
            "Processed customers are missing required columns: "
            f"{sorted(missing_columns)}"
        )

    faker = Faker()
    faker.seed_instance(AUGMENTATION_SEED)
    rng = random.Random(AUGMENTATION_SEED)

    augmented = customers.copy()

    first_names: list[str] = []
    last_names: list[str] = []
    emails: list[str] = []
    phones: list[str] = []
    addresses: list[str] = []
    channels: list[str] = []

    for row_index in range(len(augmented)):
        first_name = faker.first_name()
        last_name = faker.last_name()

        first_names.append(first_name)
        last_names.append(last_name)

        # Deterministic and guaranteed-unique across the batch, rather
        # than relying on Faker's own uniqueness tracking.
        emails.append(
            f"{first_name}.{last_name}.{row_index + 1}@example.com".lower()
        )

        phones.append(faker.phone_number()[:30])
        addresses.append(faker.street_address()[:255])
        channels.append(rng.choice(ACQUISITION_CHANNELS))

    augmented["first_name"] = first_names
    augmented["last_name"] = last_names
    augmented["email"] = emails
    augmented["phone"] = phones
    augmented["address_line_1"] = addresses
    augmented["acquisition_channel"] = channels

    if augmented["email"].duplicated().any():
        raise ValueError(
            "Generated customer emails are not unique"
        )

    return augmented[CUSTOMER_FINAL_COLUMNS]
