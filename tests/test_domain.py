from provena.domain import ALLOWED_TRANSITIONS, ClaimStatus, CredentialRole, SOURCE_AUTHORITY, SourceKind


def test_authority_does_not_promote_assistant_text():
    assert SOURCE_AUTHORITY[CredentialRole.AGENT][SourceKind.USER_STATEMENT].value == "low"
    assert SOURCE_AUTHORITY[CredentialRole.AGENT][SourceKind.ASSISTANT_INFERENCE].value == "low"
    assert SOURCE_AUTHORITY[CredentialRole.AGENT][SourceKind.HYPOTHESIS].value == "ephemeral"
    assert SOURCE_AUTHORITY[CredentialRole.HUMAN][SourceKind.USER_CORRECTION].value == "high"
    assert SOURCE_AUTHORITY[CredentialRole.TOOL][SourceKind.TEST_OUTPUT].value == "high"


def test_state_transitions_are_explicit():
    assert ClaimStatus.ACTIVE in ALLOWED_TRANSITIONS[ClaimStatus.CANDIDATE]
    assert ClaimStatus.VERIFIED not in ALLOWED_TRANSITIONS[ClaimStatus.CANDIDATE]
