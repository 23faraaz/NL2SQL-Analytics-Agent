from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
GENERATED_DATA_DIR = DATA_DIR / "generated"

# Fixed modelling assumption for this portfolio dataset.
BRL_TO_GBP_RATE = 0.15

# The Olist dataset is real historical Brazilian marketplace data. The
# canonical commerce schema does not constrain country/region values, so
# real geography is preserved rather than overwritten to fit a UK-retailer
# narrative that the source data does not represent.
SOURCE_COUNTRY = "Brazil"

# Olist's own business model was a real online marketplace connecting
# third-party sellers to buyers -- this is a documented fact about the
# dataset's provenance, applied uniformly, not a per-row guess.
SOURCE_SALES_CHANNEL = "MARKETPLACE"

# commerce.orders.status crosswalk: real Olist order_status values -> the
# canonical schema's status enum. PARTIALLY_REFUNDED/REFUNDED have no Olist
# source concept and are intentionally never produced here.
ORDER_STATUS_MAP = {
    "delivered": "DELIVERED",
    "shipped": "SHIPPED",
    "canceled": "CANCELLED",
    "processing": "PROCESSING",
    "approved": "PAID",
    "invoiced": "PAID",
    "created": "PENDING",
    # Olist's "unavailable" means the order could not be fulfilled; the
    # closest real semantic match among the target enum is CANCELLED.
    "unavailable": "CANCELLED",
}

# commerce.payments.payment_method crosswalk: real Olist payment_type
# values -> the canonical schema's payment_method enum. "not_defined" is a
# genuine small set of unlabeled source rows; CARD is used as the modal
# fallback rather than inventing a new category.
PAYMENT_METHOD_MAP = {
    "credit_card": "CARD",
    "debit_card": "CARD",
    "boleto": "BANK_TRANSFER",
    "voucher": "GIFT_CARD",
    "not_defined": "CARD",
}

# commerce.customers.acquisition_channel CHECK constraint values
# (sql/001_schema.sql). Lives here rather than in etl.augment.config so
# etl.validate.augmented can check against it without importing the
# etl.augment package (which would create a circular import through
# etl.augment.pipeline -> etl.validate.augmented).
ACQUISITION_CHANNELS = [
    "ORGANIC_SEARCH",
    "PAID_SEARCH",
    "PAID_SOCIAL",
    "ORGANIC_SOCIAL",
    "EMAIL",
    "REFERRAL",
    "INFLUENCER",
    "DIRECT",
    "AFFILIATE",
]
