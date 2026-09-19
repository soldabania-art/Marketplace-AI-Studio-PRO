"""Deterministic CI-only browser fixtures. Never run against non-ephemeral DBs."""
import os

from app.db import SessionLocal
from app.mfa_service import encrypt_secret
from app.models import Membership, MembershipRole, PlatformStaffRole, PlatformStaffRoleName, Store, User, UserMfa, Workspace
from app.security import hash_password

PASSWORD = os.environ["E2E_PASSWORD"]
TOTP_SECRET = os.environ["E2E_TOTP_SECRET"]
WORKSPACE_ID = "e2e00000-0000-4000-8000-000000000001"
STORE_A = "e2e00000-0000-4000-8000-0000000000a1"
STORE_B = "e2e00000-0000-4000-8000-0000000000b2"

def user(key, email, name):
    return User(id=key, email=email, full_name=name, password_hash=hash_password(PASSWORD), email_verified=True, is_active=True)

with SessionLocal() as db:
    workspace = Workspace(id=WORKSPACE_ID, name="E2E workspace with a deliberately long acceptance name")
    owner = user("e2e-owner", "owner.e2e@example.com", "E2E platform owner")
    manager = user("e2e-manager", "manager.e2e@example.com", "E2E project manager")
    viewer = user("e2e-viewer", "viewer.e2e@example.com", "E2E workspace viewer")
    db.add_all([workspace, owner, manager, viewer])
    # Models use scalar foreign keys rather than ORM relationships. Flush the
    # referenced rows first so PostgreSQL enforces the same fixture ordering.
    db.flush()
    db.add_all([
        Store(id=STORE_A, workspace_id=WORKSPACE_ID, name="Store A — deliberately long visible acceptance name"),
        Store(id=STORE_B, workspace_id=WORKSPACE_ID, name="Store B — deliberately long visible acceptance name"),
        Membership(user_id=owner.id, workspace_id=WORKSPACE_ID, role=MembershipRole.owner),
        Membership(user_id=manager.id, workspace_id=WORKSPACE_ID, role=MembershipRole.admin),
        Membership(user_id=viewer.id, workspace_id=WORKSPACE_ID, role=MembershipRole.analyst),
        PlatformStaffRole(user_id=owner.id, role=PlatformStaffRoleName.owner),
        PlatformStaffRole(user_id=manager.id, role=PlatformStaffRoleName.project_manager),
    ])
    for account in (owner, manager, viewer):
        db.add(UserMfa(user_id=account.id, secret_ciphertext=encrypt_secret(TOTP_SECRET), enabled=True, recovery_code_hashes=[]))
    db.commit()
