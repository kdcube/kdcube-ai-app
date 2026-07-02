from kdcube_ai_app.apps.middleware.auth import user_type_from_roles
from kdcube_ai_app.auth.sessions import UserType


def test_user_type_from_roles_marks_empty_authenticated_subject_external():
    assert user_type_from_roles([]) == UserType.EXTERNAL


def test_user_type_from_roles_marks_non_privileged_roles_registered():
    assert user_type_from_roles(["kdcube:role:registered"]) == UserType.REGISTERED


def test_user_type_from_roles_marks_admin_roles_privileged():
    assert user_type_from_roles(["kdcube:role:super-admin"]) == UserType.PRIVILEGED
