from app.services.authorization.audit_service import AuditService

def test_audit_secret_redaction(db_session):
    event = AuditService.log_event(
        db=db_session,
        event_type="test_event",
        
        
        success=True,
        metadata={"public_data": "123", "secret_key": "mysecret"}
    )
    assert event.meta["public_data"] == "123"
    assert event.meta["secret_key"] == "[REDACTED]"
