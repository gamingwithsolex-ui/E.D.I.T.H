import pytest
from edith.memory.manager import MemoryManager

def test_memory_manager_basic_flow(temp_db_path, mock_engine):
    # Using the mock engine to bypass the LLM dependency for extraction
    manager = MemoryManager(
        db_path=temp_db_path,
        engine=mock_engine
    )

    # Basic operation - since mock engine just returns fixed string, 
    # we can't test real extraction easily without more complex mocks,
    # but we can test the storage methods directly if they are public.
    assert manager.get_recent_memories() == []
