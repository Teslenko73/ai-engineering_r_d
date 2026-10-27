import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

PLACEHOLDERS = {"", "null", "none", "brak", "---", "-", "n/a", "rrrr-mm-dd"}


def _clean(v):
    """Zamienia puste wartości i placeholdery na None, obcina spacje."""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        if v.lower() in PLACEHOLDERS:
            return None
    return v


class LanguageEnum(str, Enum):
    PL = "pl"
    EN = "en"
    UNKNOWN = "unknown"


class DocumentTypeEnum(str, Enum):
    # Polskie
    WYROK = "wyrok"
    WYROK_ODWOLAWCZY = "wyrok odwoławczy"
    POSTANOWIENIE = "postanowienie"
    UZASADNIENIE = "uzasadnienie"
    ZARZADZENIE = "zarządzenie"
    # Anglojęzyczne / common law
    DECISION = "decision"
    JUDGMENT = "judgment"
    OPINION = "opinion"
    ORDER = "order"
    DECREE = "decree"
    RULING = "ruling"
    SENTENCE = "sentence"
    BRIEF = "brief"
    MEMORANDUM = "memorandum"
    # Inne
    OTHER = "other"
    UNKNOWN = "unknown"


class _CleanModel(BaseModel):
    """Baza: czyści placeholdery we wszystkich polach tekstowych."""

    @field_validator("*", mode="before")
    @classmethod
    def clean_placeholders(cls, v):
        return _clean(v)


class ParticipantsSchema(_CleanModel):
    court_clerk: Optional[str] = Field(
        default=None,
        description="Protokolant, np. 'staż. Agnieszka Księżopolska'. null jeśli brak.",
    )
    prosecutor: Optional[str] = Field(
        default=None,
        description="Prokurator obecny na posiedzeniu (przy udziale Prokuratora). "
                    "null jeśli brak lub placeholder typu '---'.",
    )


class RelatedCaseSchema(_CleanModel):
    docket_number: Optional[str] = Field(
        default=None,
        description="Sygnatura sprawy powiązanej, np. '1 Ds 1391/14'. null jeśli brak.",
    )
    authority: Optional[str] = Field(
        default=None,
        description="Organ prowadzący sprawę powiązaną, np. 'Prokuratura Rejonowa w Siedlcach'. null jeśli brak.",
    )


class OperativePartSchema(_CleanModel):
    decision: Optional[str] = Field(
        default=None,
        description="Krótkie streszczenie rozstrzygnięcia, np. 'nie uwzględnić wniosku o przepadek dowodów rzeczowych'. null jeśli brak.",
    )
    legal_basis: List[str] = Field(
        default_factory=list,
        description="Podstawy prawne rozstrzygnięcia, np. ['art. 100 kk (a contrario)', 'art. 98 § 2 kpk']. Pusta lista jeśli brak.",
    )

    @field_validator("legal_basis", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if _clean(v) else []
        return [x.strip() for x in v if isinstance(x, str) and _clean(x)]


class DocumentCoreSchema(_CleanModel):
    document_type: Optional[DocumentTypeEnum] = Field(
        default=None,
        description="Rodzaj dokumentu, np. 'postanowienie', 'wyrok', 'decision'.",
    )
    language: Optional[LanguageEnum] = Field(
        default=None,
        description="Język dokumentu: 'pl', 'en' lub 'unknown'.",
    )
    court: Optional[str] = Field(
        default=None,
        description="Pełna nazwa sądu, np. 'Sąd Rejonowy w Siedlcach'. null jeśli brak.",
    )
    division: Optional[str] = Field(
        default=None,
        description="Wydział, np. 'II Wydział Karny'. null jeśli brak.",
    )
    docket_number: Optional[str] = Field(
        default=None,
        description="Sygnatura akt bieżącej sprawy, np. 'II Kp 127/15'. null jeśli brak.",
    )
    decision_date: Optional[str] = Field(
        default=None,
        description="Data wydania orzeczenia w formacie YYYY-MM-DD, np. '2015-08-05'. null jeśli brak.",
    )
    presiding_judge: Optional[str] = Field(
        default=None,
        description="Przewodniczący składu / sędzia, np. 'SSR Daniel Kędzia'. null jeśli nie podano.",
    )
    applicant: Optional[str] = Field(
        default=None,
        description="Strona wnioskująca / wnosząca środek, np. 'Prokurator Rejonowy w Siedlcach'. "
                    "NIE mylić z protokolantem. null jeśli nieznana.",
    )
    subject_matter: Optional[str] = Field(
        default=None,
        description="Zwięzły opis przedmiotu sprawy, np. 'wniosek o orzeczenie przepadku dowodów rzeczowych tytułem środka zabezpieczającego'. null jeśli brak.",
    )

    participants: Optional[ParticipantsSchema] = None
    related_case: Optional[RelatedCaseSchema] = None
    operative_part: Optional[OperativePartSchema] = None

    @field_validator("document_type", mode="before")
    @classmethod
    def normalize_document_type(cls, v):
        if v is None:
            return None
        if isinstance(v, DocumentTypeEnum):
            return v
        try:
            return DocumentTypeEnum(str(v).strip().lower())
        except ValueError:
            return DocumentTypeEnum.OTHER

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, v):
        if v is None:
            return None
        if isinstance(v, LanguageEnum):
            return v
        try:
            return LanguageEnum(str(v).strip().lower())
        except ValueError:
            return LanguageEnum.UNKNOWN

    @field_validator("decision_date", mode="after")
    @classmethod
    def validate_date(cls, v):
        if v is None:
            return None
        return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None


class UnifiedRulingSchema(BaseModel):
    document: DocumentCoreSchema
# from enum import Enum
# from typing import List, Optional
# from pydantic import BaseModel, Field, field_validator
# 
# 
# # 1. Enums (Requirement: at least 1 Enum)
# class LanguageEnum(str, Enum):
#     PL = "pl"
#     EN = "en"
#     UNKNOWN = "unknown"
# 
# 
# class DocumentTypeEnum(str, Enum):
#     # --- Dokumenty Polskie ---
#     WYROK = "wyrok"
#     WYROK_ODWOLAWCZY = "wyrok odwoławczy"
#     POSTANOWIENIE = "postanowienie"
#     UZASADNIENIE = "uzasadnienie"
#     ZARZADZENIE = "zarządzenie"
# 
#     # --- Dokumenty Anglojęzyczne / Common Law ---
#     DECISION = "decision"  # Ogólne orzeczenie / decyzja
#     JUDGMENT = "judgment"  # Wyrok końcowy
#     OPINION = "opinion"  # Uzasadnienie / opinia sądu (bardzo częste w USA, np. Per Curiam, Majority Opinion)
#     ORDER = "order"  # Postanowienie / nakaz sądowy
#     DECREE = "decree"  # Dekret / wyrok (często w sprawach cywilnych/rodzinnych)
#     RULING = "ruling"  # Rozstrzygnięcie / orzeczenie
#     SENTENCE = "sentence"  # Wyrok skazujący / wymiar kary
#     BRIEF = "brief"  # Pismo procesowe / apelacja
#     MEMORANDUM = "memorandum"  # Notatka prawna / decyzja ze zwięzłym uzasadnieniem
# 
#     # --- Inne / Inne języki ---
#     OTHER = "other"
#     UNKNOWN = "unknown"
# 
# 
# # 2. Nested Models (małe, 2 pola każdy)
# class ParticipantsSchema(BaseModel):
#     court_clerk: Optional[str] = Field(
#         default=None,
#         description="Name of the court clerk (protokolant), e.g. 'staż. Agnieszka Księżopolska'. Set to null if missing.",
#     )
#     prosecutor: Optional[str] = Field(
#         default=None,
#         description="Name of the prosecutor present at the hearing (przy udziale Prokuratora). "
#                     "Set to null if missing or if only a placeholder like '---' is given.",
#     )
# 
# 
# class RelatedCaseSchema(BaseModel):
#     docket_number: Optional[str] = Field(
#         default=None,
#         description="Docket number of the related/underlying case referenced in the document "
#                     "(e.g. '1 Ds 1391/14' for the prosecutor's investigation). Set to null if missing.",
#     )
#     authority: Optional[str] = Field(
#         default=None,
#         description="Court or authority that handled the related case (e.g. Prokuratura Rejonowa). Set to null if missing.",
#     )
# 
# 
# class OperativePartSchema(BaseModel):
#     decision: Optional[str] = Field(
#         default=None,
#         description="Short summary of what the court decided in the operative part "
#                     "(e.g. 'nie uwzględnić wniosku o przepadek dowodów rzeczowych'). Set to null if missing.",
#     )
#     legal_basis: List[str] = Field(
#         default_factory=list,
#         description="Legal provisions cited as the basis of the decision "
#                     "(e.g. ['art. 100 kk (a contrario)', 'art. 98 § 2 kpk']). Empty list if none.",
#     )
# 
# 
# # 3. Core Document Schema (pola płaskie zgodne z golden setem + zagnieżdżone)
# class DocumentCoreSchema(BaseModel):
#     document_type: Optional[DocumentTypeEnum] = Field(
#         default=None,
#         description="Type of the legal document (e.g., wyrok, postanowienie, UZASADNIENIE, decision).",
#     )
#     language: Optional[LanguageEnum] = Field(
#         default=None,
#         description="Language of the document (e.g., pl, en).",
#     )
#     court: Optional[str] = Field(
#         default=None,
#         description="Full official name of the court issuing this document. Set to null if not present.",
#     )
#     division: Optional[str] = Field(
#         default=None,
#         description="Court division or chamber (e.g., VII Wydział Karny Odwoławczy, Wydział I Cywilny). Set to null if not present.",
#     )
#     docket_number: Optional[str] = Field(
#         default=None,
#         description="Main docket number (sygnatura akt) of the current proceedings (e.g., VII Ka 152/16). Set to null if not present.",
#     )
#     decision_date: Optional[str] = Field(
#         default=None,
#         description="Date when the ruling was issued in YYYY-MM-DD format (e.g. 2015-08-05). Set to null if missing.",
#     )
#     presiding_judge: Optional[str] = Field(
#         default=None,
#         description="Name of the presiding judge. Set to null if not explicitly mentioned.",
#     )
#     applicant: Optional[str] = Field(
#         default=None,
#         description="Party or entity initiating the appeal or filing the request (e.g., obrońca oskarżonego, prokurator, powódka). Do NOT confuse with the court clerk/protokolant. Set to null if unknown.",
#     )
#     subject_matter: Optional[str] = Field(
#         default=None,
#         description="Concise description of the subject matter or reason for appeal/proceeding. Set to null if missing.",
#     )
# 
#     # Zagnieżdżone struktury
#     participants: Optional[ParticipantsSchema] = None
#     related_case: Optional[RelatedCaseSchema] = None
#     operative_part: Optional[OperativePartSchema] = None
# 
#     # 🛡️ ZABEZPIECZENIE 1: Obsługa wielkich liter w Enum
#     @field_validator("document_type", mode="before")
#     @classmethod
#     def normalize_document_type(cls, v):
#         if not v:
#             return None
#         if isinstance(v, str):
#             v_lower = v.strip().lower()
#             # Próbujemy dopasować do naszego Enuma, a jak nie ma, dajemy 'other'
#             try:
#                 return DocumentTypeEnum(v_lower)
#             except ValueError:
#                 return DocumentTypeEnum.OTHER
#         return v
# 
#     # 🛡️ ZABEZPIECZENIE 2: Bezpieczna data (nie wywala błędu, jak model napisze głupotę)
#     @field_validator("decision_date", mode="before")
#     @classmethod
#     def parse_date_safely(cls, v):
#         if not v or v in ["null", "None", "RRRR-MM-DD", "brak"]:
#             return None
#         return v
# 
# 
# class UnifiedRulingSchema(BaseModel):
#     document: DocumentCoreSchema
