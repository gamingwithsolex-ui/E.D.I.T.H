import pytest
import time
from edith.sessions.session import SessionStore

def test_session_store_create(temp_db_path):
    store = SessionStore(db_path=temp_db_path)
    session = store.get_or_create(user_id="user1", display_name="Alice")
    
    assert session.identity.user_id == "user1"
    assert session.identity.display_name == "Alice"
    assert len(session.messages) == 0

def test_session_store_save_message(temp_db_path):
    store = SessionStore(db_path=temp_db_path)
    session = store.get_or_create(user_id="user1")
    
    store.save_message(
        session_id=session.session_id,
        role="user",
        content="Hello"
    )
    
    session2 = store.get_or_create(user_id="user1")
    assert len(session2.messages) == 1
    assert session2.messages[0].role == "user"
    assert session2.messages[0].content == "Hello"

def test_session_store_decay(temp_db_path):
    store = SessionStore(db_path=temp_db_path, max_age_hours=0.0001)
    store.get_or_create(user_id="user1")
    
    # Wait for session to expire
    time.sleep(0.5)
    
    removed = store.decay()
    assert removed == 1
