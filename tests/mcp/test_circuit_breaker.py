import pytest
import time
from edith.mcp.reliability.circuit_breaker import CircuitBreaker, CircuitState

def test_circuit_breaker_state_transitions():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    
    # Initial state
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute("test_server") is True
    
    # Record failures
    cb.record_failure("test_server", Exception("err1"))
    cb.record_failure("test_server", Exception("err2"))
    assert cb.state == CircuitState.CLOSED
    
    # Trip breaker
    cb.record_failure("test_server", Exception("err3"))
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute("test_server") is False
    
    # Wait for recovery
    time.sleep(0.15)
    assert cb.can_execute("test_server") is True
    assert cb.state == CircuitState.HALF_OPEN
    
    # Success in half-open resets to closed
    cb.record_success("test_server")
    assert cb.state == CircuitState.CLOSED
