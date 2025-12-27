"""
Comprehensive Pydantic models for GoCardless API responses
Complete coverage of all schemas from swagger.json
"""

from typing import Optional, List, Dict, Any, TypedDict
from pydantic import BaseModel, Field, ConfigDict, validator
from pydantic.alias_generators import to_camel
from enum import Enum


class AccountInfo(TypedDict, total=False):
    id: str
    created: str
    last_accessed: Optional[str]
    iban: Optional[str]
    bban: Optional[str]
    status: str
    institution_id: Optional[str]
    owner_name: Optional[str]
    name: Optional[str]
    requisition_id: str
    requisition_reference: str


class StatusEnum(str, Enum):
    """Status enumeration for various API responses."""

    LN = "LN"
    RJ = "RJ"
    ER = "ER"
    UR = "UR"
    GA = "GA"
    SA = "SA"


class BalanceAmountSchema(BaseModel):
    """Balance amount schema."""

    amount: str
    currency: str


class BalanceSchema(BaseModel):
    """Balance schema."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    balance_amount: BalanceAmountSchema
    balance_type: str
    credit_limit_included: Optional[bool] = None
    last_change_date_time: Optional[str] = None
    last_committed_transaction: Optional[str] = None
    reference_date: Optional[str] = None


class AccountBalance(BaseModel):
    """Account balance response."""

    balances: List[BalanceSchema]


class Account(BaseModel):
    """Account model - complete from swagger."""

    id: str = Field(
        description="The ID of this Account, used to refer to this account in other API calls."
    )
    created: str = Field(
        description="The date & time at which the account object was created."
    )
    last_accessed: Optional[str] = Field(
        None,
        description="The date & time at which the account object was last accessed.",
    )
    iban: Optional[str] = Field(None, description="The Account IBAN")
    bban: Optional[str] = Field(None, description="The Account BBAN")
    status: str = Field(description="The processing status of this account.")
    institution_id: Optional[str] = Field(
        None, description="The ASPSP associated with this account."
    )
    owner_name: Optional[str] = Field(
        None, description="The name of the account owner."
    )
    name: Optional[str] = Field(None, description="The name of account.")


class AccountSchema(BaseModel):
    """Account schema for requests."""

    iban: Optional[str] = Field(None, description="iban")
    bban: Optional[str] = Field(None, description="bban")
    pan: Optional[str] = Field(None, description="pan")
    masked_pan: Optional[str] = Field(None, description="maskedPan")
    msisdn: Optional[str] = Field(None, description="msisdn")
    currency: Optional[str] = Field(None, description="currency")


class AdditionalAccountDataSchema(BaseModel):
    """Additional account data schema."""

    owner_name: Optional[List[str]] = Field(
        None, description="Name(s) of the account owner. Multiple names are possible."
    )
    display_name: Optional[str] = Field(
        None, description="Display name of the account."
    )
    product: Optional[str] = Field(None, description="Product name of the account.")
    cash_account_type: Optional[str] = Field(None, description="Cash account type.")
    status: Optional[str] = Field(None, description="Account status.")
    bic: Optional[str] = Field(None, description="BIC associated with the account.")
    linked_accounts: Optional[List[str]] = Field(
        None, description="List of linked account IDs."
    )
    usage: Optional[str] = Field(None, description="Usage type of the account.")
    details: Optional[str] = Field(
        None, description="Additional details about the account."
    )


class OwnerAddressStructuredSchema(BaseModel):
    """Owner address structured schema."""

    street_name: Optional[str] = Field(None, description="Street name.")
    building_number: Optional[str] = Field(None, description="Building number.")
    town_name: Optional[str] = Field(None, description="Town name.")
    post_code: Optional[str] = Field(None, description="Post code.")
    country: Optional[str] = Field(None, description="Country.")


class DetailSchema(BaseModel):
    """Detail schema for account details."""

    resource_id: Optional[str] = Field(None, description="Resource ID.")
    iban: Optional[str] = Field(None, description="IBAN.")
    bban: Optional[str] = Field(None, description="BBAN.")
    pan: Optional[str] = Field(None, description="PAN.")
    masked_pan: Optional[str] = Field(None, description="Masked PAN.")
    msisdn: Optional[str] = Field(None, description="MSISDN.")
    currency: Optional[str] = Field(None, description="Currency.")
    owner_name: Optional[List[str]] = Field(None, description="Owner name(s).")
    name: Optional[str] = Field(None, description="Account name.")
    display_name: Optional[str] = Field(None, description="Display name.")
    product: Optional[str] = Field(None, description="Product.")
    cash_account_type: Optional[str] = Field(None, description="Cash account type.")
    status: Optional[str] = Field(None, description="Status.")
    bic: Optional[str] = Field(None, description="BIC.")
    linked_accounts: Optional[List[str]] = Field(None, description="Linked accounts.")
    usage: Optional[str] = Field(None, description="Usage.")
    details: Optional[str] = Field(None, description="Details.")
    balances: Optional[List[BalanceSchema]] = Field(None, description="Balances.")
    owner_address_structured: Optional[OwnerAddressStructuredSchema] = Field(
        None, description="Owner address."
    )
    owner_address_unstructured: Optional[List[str]] = Field(
        None, description="Owner address unstructured."
    )


class AccountDetail(BaseModel):
    """Account detail response."""

    account: DetailSchema


class TransactionAmountSchema(BaseModel):
    """Transaction amount schema."""

    amount: str
    currency: str


class InstructedAmount(BaseModel):
    """Instructed amount schema."""

    amount: str
    currency: str


class CurrencyExchangeSchema(BaseModel):
    """Currency exchange schema."""

    source_currency: str
    exchange_rate: Optional[str] = None
    unit_currency: Optional[str] = None
    target_currency: Optional[str] = None
    quotation_date: Optional[str] = None
    contract_identification: Optional[str] = None
    instructed_amount: Optional[InstructedAmount] = None


class BalanceAfterTransactionSchema(BaseModel):
    """Balance after transaction schema."""

    balance_after_transaction: Optional[BalanceAmountSchema] = None
    balance_type: Optional[str] = None


class TransactionSchema(BaseModel):
    """Transaction schema."""

    transaction_id: Optional[str] = Field(None, description="Transaction ID.")
    booking_date: Optional[str] = Field(None, description="Booking date.")
    booking_date_time: Optional[str] = Field(None, description="Booking date and time.")
    value_date: Optional[str] = Field(None, description="Value date.")
    value_date_time: Optional[str] = Field(None, description="Value date and time.")
    transaction_amount: TransactionAmountSchema
    currency_exchange: Optional[List[CurrencyExchangeSchema]] = None
    creditor_name: Optional[str] = Field(None, description="Creditor name.")
    creditor_account: Optional[AccountSchema] = None
    creditor_agent: Optional[str] = Field(None, description="Creditor agent.")
    ultimate_creditor: Optional[str] = Field(None, description="Ultimate creditor.")
    debtor_name: Optional[str] = Field(None, description="Debtor name.")
    debtor_account: Optional[AccountSchema] = None
    debtor_agent: Optional[str] = Field(None, description="Debtor agent.")
    ultimate_debtor: Optional[str] = Field(None, description="Ultimate debtor.")
    remittance_information_unstructured: Optional[str] = Field(
        None, description="Unstructured remittance information."
    )
    remittance_information_structured: Optional[str] = Field(
        None, description="Structured remittance information."
    )
    additional_information: Optional[str] = Field(
        None, description="Additional information."
    )
    balance_after_transaction: Optional[BalanceAfterTransactionSchema] = None
    bank_transaction_code: Optional[str] = Field(
        None, description="Bank transaction code."
    )
    proprietary_bank_transaction_code: Optional[str] = Field(
        None, description="Proprietary bank transaction code."
    )
    internal_transaction_id: Optional[str] = Field(
        None, description="Internal transaction ID."
    )


class BankTransaction(BaseModel):
    """Bank transaction - complete transaction model."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    transaction_id: Optional[str] = Field(
        None, description="Unique transaction identifier."
    )
    debtor_name: Optional[str] = Field(None, description="Debtor name.")
    debtor_account: Optional[AccountSchema] = None
    transaction_amount: Optional[TransactionAmountSchema] = None
    booking_date: Optional[str] = Field(None, description="Booking date.")
    value_date: Optional[str] = Field(None, description="Value date.")
    remittance_information_unstructured: Optional[str] = Field(
        None, description="Unstructured remittance information."
    )
    remittance_information_structured: Optional[str] = Field(
        None, description="Structured remittance information."
    )
    additional_information: Optional[str] = Field(
        None, description="Additional information."
    )
    creditor_name: Optional[str] = Field(None, description="Creditor name.")
    creditor_account: Optional[AccountSchema] = None
    currency_exchange: Optional[List[CurrencyExchangeSchema]] = None
    balance_after_transaction: Optional[BalanceAfterTransactionSchema] = None
    bank_transaction_code: Optional[str] = Field(
        None, description="Bank transaction code."
    )
    proprietary_bank_transaction_code: Optional[str] = Field(
        None, description="Proprietary bank transaction code."
    )
    internal_transaction_id: Optional[str] = Field(
        None, description="Internal transaction ID."
    )
    remittance_information_unstructured_array: Optional[List[str]] = Field(
        None, description="Unstructured remittance information array."
    )
    booking_date_time: Optional[str] = Field(None, description="Booking date and time.")
    value_date_time: Optional[str] = Field(None, description="Value date and time.")
    entry_reference: Optional[str] = Field(None, description="Entry reference.")
    additional_information_structured: Optional[str] = Field(
        None, description="Additional structured information."
    )
    card_transaction: Optional[Dict[str, Any]] = Field(
        None, description="Card transaction details."
    )
    merchant_category_code: Optional[str] = Field(
        None, description="Merchant category code."
    )
    creditor_id: Optional[str] = Field(None, description="Creditor ID.")
    mandate_id: Optional[str] = Field(None, description="Mandate ID.")
    transaction_status: Optional[str] = Field(None, description="Transaction status.")
    funds_code: Optional[str] = Field(None, description="Funds code.")
    batch_booking_indicator: Optional[bool] = Field(
        None, description="Batch booking indicator."
    )
    number_of_transactions: Optional[int] = Field(
        None, description="Number of transactions."
    )
    account_servicer_reference: Optional[str] = Field(
        None, description="Account servicer reference."
    )


class AccountTransactions(BaseModel):
    """Account transactions response - complete with all fields."""

    transactions: Dict[str, List[BankTransaction]]  # booked and pending
    last_updated: Optional[str] = Field(
        None, description="The last time the account transactions were updated"
    )


class Institution(BaseModel):
    """Institution model - complete from swagger."""

    id: str
    name: str
    bic: Optional[str] = None
    transaction_total_days: str
    countries: List[str]
    logo: Optional[str] = None
    total_countries: Optional[int] = None
    supported_payments: Optional[Dict[str, Any]] = None
    supported_features: Optional[List[str]] = None


class RequisitionRequest(BaseModel):
    """Requisition request - complete model."""

    redirect: str
    institution_id: str
    reference: str
    agreement: Optional[str] = None
    user_language: Optional[str] = None
    ssn: Optional[str] = None
    redirect_immediate: Optional[bool] = None
    account_selection: Optional[bool] = None
    redirect_uri: Optional[str] = None
    access_valid_for_days: Optional[int] = None
    max_historical_days: Optional[int] = None
    access_scope: Optional[List[str]] = None
    additional_id: Optional[str] = None
    accounts: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class Requisition(BaseModel):
    """Requisition model - complete from swagger."""

    id: str
    created: str
    redirect: str
    status: str
    institution_id: str
    agreement: Optional[str] = None
    reference: str
    accounts: List[str] = []
    user_language: Optional[str] = None
    link: Optional[str] = None
    ssn: Optional[str] = None
    account_selection: Optional[bool] = None
    redirect_immediate: Optional[bool] = None
    enduser_agreement_id: Optional[str] = None
    authentication_user_id: Optional[str] = None
    redirect_uri: Optional[str] = None
    access_valid_for_days: Optional[int] = None
    max_historical_days: Optional[int] = None
    access_scope: Optional[List[str]] = None
    additional_id: Optional[str] = None


class SpectacularRequisition(BaseModel):
    """Spectacular requisition - API documentation model."""

    id: str
    created: str
    redirect: str
    status: str
    institution_id: str
    agreement: Optional[str] = None
    reference: str
    accounts: List[str]
    user_language: Optional[str] = None
    link: Optional[str] = None
    ssn: Optional[str] = None
    account_selection: Optional[bool] = None
    redirect_immediate: Optional[bool] = None
    enduser_agreement_id: Optional[str] = None


class PaginatedRequisitionList(BaseModel):
    """Paginated requisition list."""

    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[Requisition]


class EndUserAgreementRequest(BaseModel):
    """End user agreement request."""

    institution_id: str
    max_historical_days: int
    access_valid_for_days: int
    access_scope: List[str]
    accepted_usage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class EndUserAgreement(BaseModel):
    """End user agreement - complete model."""

    id: str
    created: str
    accepted: Optional[str] = None
    institution_id: str
    max_historical_days: int
    access_valid_for_days: int
    access_scope: List[str]
    accepted_usage: Optional[str] = None
    locale: Optional[str] = None
    access_valid_until: Optional[str] = None
    accepted_at: Optional[str] = None


class PaginatedEndUserAgreementList(BaseModel):
    """Paginated end user agreement list."""

    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[EndUserAgreement]


class EnduserAcceptanceDetailsRequest(BaseModel):
    """End user acceptance details request."""

    user_agent: str
    ip: str
    accepted: Optional[bool] = None


class ReconfirmationRetrieveRequest(BaseModel):
    """Reconfirmation retrieve request."""

    user_agent: str
    ip: str
    redirect: Optional[str] = None


class ReconfirmationRetrieve(BaseModel):
    """Reconfirmation retrieve response."""

    reconfirmation_id: str
    created: str
    accounts: List[str]
    redirect: Optional[str] = None


class SuccessfulDeleteResponse(BaseModel):
    """Successful delete response."""

    summary: str
    detail: str
    status_code: int


class ErrorResponse(BaseModel):
    """Error response model."""

    summary: str
    detail: str
    status_code: int


class JWTObtainPairRequest(BaseModel):
    """JWT obtain pair request."""

    secret_id: str
    secret_key: str


class JWTRefreshRequest(BaseModel):
    """JWT refresh request."""

    refresh: str


class SpectacularJWTRefresh(BaseModel):
    """Spectacular JWT refresh response."""

    access: str
    access_expires: int
    refresh: str
    refresh_expires: int


class SpectacularJWTObtain(BaseModel):
    """Spectacular JWT obtain response."""

    refresh: str
    access: str
    access_expires: int
    refresh_expires: int


class Integration(BaseModel):
    """Integration model."""

    id: str
    name: str
    bic: Optional[str] = None
    transaction_total_days: str
    max_access_valid_for_days: Optional[int] = None
    countries: List[str]
    logo: Optional[str] = None
    supported_payments: Optional[Dict[str, Any]] = None
    supported_features: Optional[List[str]] = None
    identification_codes: Optional[List[str]] = None


class IntegrationRetrieve(BaseModel):
    """Integration retrieve response."""

    id: str
    name: str
    bic: Optional[str] = None
    transaction_total_days: str
    max_access_valid_for_days: Optional[int] = None
    countries: List[str]
    logo: Optional[str] = None
    supported_payments: Optional[Dict[str, Any]] = None
    supported_features: Optional[List[str]] = None
    identification_codes: Optional[List[str]] = None


class AccountConfig(BaseModel):
    id: str
    asset_account: str
    metadata: Dict[str, Any] = {}
    transaction_types: List[str] = ["booked", "pending"]

    @validator("transaction_types")
    def validate_transaction_types(cls, v):
        allowed = {"booked", "pending"}
        if not set(v).issubset(allowed):
            raise ValueError(
                f"Invalid transaction types: {v}. Must be subset of {allowed}"
            )
        return v


class GoCardlessConfig(BaseModel):
    secret_id: str
    secret_key: str
    cache_options: Dict[str, Any] = {}
    accounts: List[AccountConfig]
