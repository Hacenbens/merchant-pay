from dataclasses import dataclass, replace

from app.contexts.identity.application.ports import (
    AccessRepository,
    AuditLog,
    MerchantRepository,
    PasswordHasher,
    TokenService,
    UserRepository,
)
from app.contexts.identity.domain.model import Merchant, MerchantAccess, Role, User
from app.shared.domain.errors import DomainError, Forbidden, InvalidCredentials, NotFound
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.money import Money


class Authenticate:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService) -> None:
        self._users, self._hasher, self._tokens = users, hasher, tokens

    def execute(self, email: str, password: str) -> str:
        user = self._users.get_by_email(email.strip().lower())
        if user is None or not user.is_active or not self._hasher.verify(password, user.password_hash):
            raise InvalidCredentials()  # same error whatever failed: no account enumeration
        return self._tokens.issue(user.id)


class ResolveScope:
    """The ONLY producer of MerchantScope. Server-side mapping is the authority."""

    def __init__(self, access: AccessRepository) -> None:
        self._access = access

    def execute(self, user_id: int, requested_merchant_id: str | None = None) -> MerchantScope:
        grants = self._access.for_user(user_id)
        if not grants:
            raise Forbidden("No merchant assigned to this user")
        if requested_merchant_id is None:
            grant = grants[0]
        else:
            grant = next((g for g in grants if g.merchant_id == requested_merchant_id), None)
            if grant is None:
                raise Forbidden("Merchant not accessible")
        return MerchantScope(user_id=user_id, merchant_id=grant.merchant_id, role=grant.role.value)


@dataclass(frozen=True, slots=True)
class Me:
    user: User
    merchant: Merchant
    accessible: list[MerchantAccess]


class GetMe:
    def __init__(self, users: UserRepository, access: AccessRepository,
                 merchants: MerchantRepository) -> None:
        self._users, self._access, self._merchants = users, access, merchants

    def execute(self, scope: MerchantScope) -> Me:
        user = self._users.get(scope.user_id)
        merchant = self._merchants.get(scope.merchant_id)
        if user is None or merchant is None:
            raise NotFound("Profile not found")
        return Me(user, merchant, self._access.for_user(scope.user_id))


WEEKDAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")


@dataclass(frozen=True, slots=True)
class ProfileChanges:
    """Only the fields the merchant actually sent; None means "leave unchanged"."""

    display_name: str | None = None
    category: str | None = None
    operating_days: tuple[str, ...] | None = None
    monthly_goal: Money | None = None
    clear_monthly_goal: bool = False


class UpdateMerchantProfile:
    """Owner-only profile edit. Writes an audit event naming the changed fields (not their values)."""

    def __init__(self, merchants: MerchantRepository, audit: AuditLog) -> None:
        self._merchants, self._audit = merchants, audit

    def execute(self, scope: MerchantScope, changes: ProfileChanges) -> Merchant:
        if scope.role != Role.OWNER.value:
            raise Forbidden("Only the merchant owner can edit the profile")
        merchant = self._merchants.get(scope.merchant_id)
        if merchant is None:
            raise NotFound("Merchant not found")

        updates: dict[str, object] = {}
        if changes.display_name is not None:
            name = changes.display_name.strip()
            if not name:
                raise DomainError("Display name cannot be empty")
            updates["display_name"] = name
        if changes.category is not None:
            updates["category"] = changes.category.strip()
        if changes.operating_days is not None:
            unknown = set(changes.operating_days) - set(WEEKDAYS)
            if unknown or not changes.operating_days:
                raise DomainError("Operating days must be a non-empty subset of sun..sat")
            updates["operating_days"] = tuple(d for d in WEEKDAYS if d in changes.operating_days)
        if changes.clear_monthly_goal:
            updates["monthly_goal"] = None
        elif changes.monthly_goal is not None:
            if changes.monthly_goal.centimes <= 0:
                raise DomainError("Monthly goal must be positive")
            updates["monthly_goal"] = changes.monthly_goal

        if not updates:
            return merchant
        updated = replace(merchant, **updates)
        self._merchants.save(updated)
        self._audit.record(scope.user_id, "merchant.profile_updated",
                           f"merchant:{merchant.merchant_id} fields:{','.join(sorted(updates))}")
        return updated
