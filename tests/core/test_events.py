import pytest
from edith.core.events import EventBus, EventType

def test_event_bus_publish_subscribe():
    bus = EventBus()
    received_events = []

    def handler(event):
        received_events.append(event)

    bus.subscribe(EventType.USER_MESSAGE, handler)

    bus.publish(EventType.USER_MESSAGE, {"text": "Hello"})
    bus.publish(EventType.TOOL_EXECUTION, {"tool": "dummy"})

    assert len(received_events) == 1
    assert received_events[0].event_type == EventType.USER_MESSAGE
    assert received_events[0].data["text"] == "Hello"

def test_event_bus_unsubscribe():
    bus = EventBus()
    received_events = []

    def handler(event):
        received_events.append(event)

    bus.subscribe(EventType.USER_MESSAGE, handler)
    bus.unsubscribe(EventType.USER_MESSAGE, handler)

    bus.publish(EventType.USER_MESSAGE, {"text": "Hello"})

    assert len(received_events) == 0
