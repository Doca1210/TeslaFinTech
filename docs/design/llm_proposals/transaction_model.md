# Transaction Model — Sanctions Screening

This document defines the canonical transaction data model used as input to the screening engine. It reflects what regulatory bodies and compliance teams actually receive and inspect, based on SWIFT MT103, ISO 20022 (pacs.008), SEPA Credit Transfer, and FATF Travel Rule for crypto.

---

## Fiat Transaction

```python
@dataclass
class Party:
    full_name: str                  # Legal name as on account
    name_aliases: list[str]         # Alt spellings, nicknames, trading names
    account_number: str             # IBAN or local account format
    account_type: str               # "IBAN" | "BBAN" | "CLABE" | "BBAN_US"
    national_id: str | None         # Passport, SSN, TIN, company registration
    date_of_birth: date | None      # For individuals
    country_of_residence: str       # ISO 3166-1 alpha-2
    address: Address | None
    entity_type: str                # "INDIVIDUAL" | "COMPANY" | "GOVERNMENT"

@dataclass
class Address:
    street: str | None
    city: str | None
    country: str                    # ISO 3166-1 alpha-2
    postal_code: str | None

@dataclass
class FinancialInstitution:
    bic: str                        # BIC/SWIFT code (8 or 11 chars)
    name: str
    country: str                    # ISO 3166-1 alpha-2
    routing_number: str | None      # ABA (US), Sort Code (UK), etc.

@dataclass
class FiatTransaction:
    # Identifiers
    transaction_id: str             # Internal unique ID
    uetr: str                       # ISO 20022 Unique End-to-End Transaction Reference (UUID4)
    instruction_id: str             # Sender's reference (MT103 Field 20)
    end_to_end_id: str              # End-to-end reference

    # Parties
    originator: Party               # Sender (MT103 Field 50)
    beneficiary: Party              # Receiver (MT103 Field 59)

    # Routing chain
    originator_bank: FinancialInstitution   # Sender's bank (MT103 Field 52)
    beneficiary_bank: FinancialInstitution  # Receiver's bank (MT103 Field 57)
    intermediary_bank: FinancialInstitution | None  # Correspondent (MT103 Field 56)
    correspondent_bank: FinancialInstitution | None # MT103 Field 53/54

    # Value
    amount: Decimal
    currency: str                   # ISO 4217 (e.g. "USD", "EUR", "GBP")
    settlement_amount: Decimal | None       # Amount after FX conversion
    settlement_currency: str | None

    # Temporal
    value_date: date                # Settlement date (MT103 Field 32A)
    created_at: datetime            # When the payment instruction was created
    submitted_at: datetime          # When submitted to the network

    # Purpose & metadata
    purpose_code: str | None        # ISO 20022 purpose code (e.g. "SALA", "SUPP", "INTC")
    remittance_info: str | None     # Free-text payment reference (MT103 Field 70)
    regulatory_reporting: list[RegulatoryField]  # MT103 Field 77B

    # Channel
    payment_rail: str               # "SWIFT" | "SEPA" | "ACH" | "BACS" | "CHAPS" | "RTP"
    priority: str                   # "URGENT" | "NORMAL" | "BATCH"

    # Screening context (populated at intake)
    countries_in_scope: list[str]   # All countries touched (originator, beneficiary, banks)
    raw_payload: dict               # Original message verbatim for audit

@dataclass
class RegulatoryField:
    country: str
    code: str
    info: str
```

---

## Crypto Transaction

```python
@dataclass
class CryptoParty:
    wallet_address: str             # Chain-specific address
    address_type: str               # "EOA" | "CONTRACT" | "MULTISIG" | "EXCHANGE_DEPOSIT"
    chain: str                      # "ETHEREUM" | "BITCOIN" | "SOLANA" | "TRON" | ...
    vasp_name: str | None           # Virtual Asset Service Provider (exchange name)
    vasp_did: str | None            # FATF Travel Rule VASP DID
    # FATF Travel Rule fields (required for transfers >= $1000 / 1000 EUR)
    owner_name: str | None          # Beneficial owner name (Travel Rule)
    owner_national_id: str | None
    owner_dob: date | None
    owner_address: Address | None

@dataclass
class CryptoTransaction:
    # Identifiers
    transaction_id: str             # Internal unique ID
    tx_hash: str                    # On-chain transaction hash
    block_number: int | None
    block_timestamp: datetime | None

    # Parties
    originator: CryptoParty
    beneficiary: CryptoParty

    # Value
    amount: Decimal
    asset: str                      # "ETH" | "BTC" | "USDC" | "SOL" | ...
    asset_contract: str | None      # ERC-20 contract address if token
    usd_equivalent: Decimal | None  # USD value at time of transaction

    # Temporal
    submitted_at: datetime          # When broadcast to mempool
    confirmed_at: datetime | None

    # Screening context
    chain: str
    raw_payload: dict               # Raw node/API response
```

---

## Screening Request

Unified input to the screening engine regardless of payment type:

```python
@dataclass
class ScreeningRequest:
    request_id: str                 # Idempotency key
    payment_type: str               # "FIAT" | "CRYPTO"
    transaction: FiatTransaction | CryptoTransaction
    screening_lists: list[str]      # Which lists to check: ["OFAC_SDN", "EU", "UN", "OFSI", "PEP"]
    requested_at: datetime
    caller_system: str              # Which upstream system submitted this
    # Optional behavioral context
    entity_history_id: str | None   # If known entity, for anomaly comparison
```

---

## Screening Verdict

```python
@dataclass
class ScreeningVerdict:
    request_id: str
    verdict: str                    # "MATCH" | "REVIEW" | "NO_MATCH"
    confidence: float               # 0.0 - 1.0
    latency_ms: int                 # Time to produce verdict

    # What triggered the verdict
    hits: list[ScreeningHit]

    # Explainability (regulatory audit requirement)
    explanation: str                # Human-readable summary
    lists_checked: list[str]
    checked_at: datetime
    model_version: str              # Version of screening engine

@dataclass
class ScreeningHit:
    matched_entity_id: str          # ID of entity in sanctions list
    matched_entity_name: str
    list_source: str                # "OFAC_SDN" | "EU" | "UN" | "OFSI" | "PEP"
    match_type: str                 # "EXACT" | "FUZZY_NAME" | "PHONETIC" | "EMBEDDING" | "WALLET" | "GRAPH_HOP"
    match_field: str                # Which field matched: "name" | "account" | "wallet" | "alias"
    similarity_score: float         # 0.0 - 1.0
    hop_distance: int | None        # For graph-based crypto hits
    evidence: dict                  # Raw match detail for audit log
```

---

## What Regulatory Lists Publish (Entity Schema)

What OFAC, EU, UN, OFSI actually publish per sanctioned entity:

```python
@dataclass
class SanctionedEntity:
    entity_id: str                  # List-specific ID (e.g. OFAC SDN ID)
    list_source: str
    entity_type: str                # "INDIVIDUAL" | "ENTITY" | "VESSEL" | "AIRCRAFT"
    
    # Identity
    primary_name: str
    aliases: list[str]              # All known aliases, transliterations, prior names
    date_of_birth: date | None
    place_of_birth: str | None
    nationalities: list[str]
    national_ids: list[str]         # Passport numbers, ID numbers
    
    # Corporate
    registration_numbers: list[str]
    registration_country: str | None
    
    # Addresses
    addresses: list[Address]
    
    # Financial identifiers
    account_numbers: list[str]
    wallet_addresses: list[str]     # OFAC publishes sanctioned ETH/BTC addresses
    
    # Program context
    programs: list[str]             # Sanction programs (e.g. "UKRAINE-EO13685", "IRAN")
    listed_on: date
    last_updated: date
    
    # Source metadata
    source_url: str
    raw_record: dict
```

---

## Key Observations for Screening Design

1. **Name is the weakest field** — free text, no format validation, varies across transliteration systems.
2. **Account number is the strongest field** — if available, IBAN/wallet match is near-exact.
3. **All countries touched** must be checked, not just sender/receiver — intermediary banks can route through sanctioned jurisdictions.
4. **Aliases multiply the search space** — a single OFAC entry can have 40+ name variants (Gaddafi has ~30 official spellings).
5. **Travel Rule data is sparse** — crypto VASP identity fields are often missing for non-custodial wallets.
6. **Settlement date ≠ instruction date** — screening must happen before settlement (T+0 for RTP, T+2 for ACH).
