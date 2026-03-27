from lib.eventhook import EventHook


def test_add_and_fire():
    hook = EventHook()
    results = []
    hook.addHandler(lambda x: results.append(x))
    hook.fire("hello")
    assert results == ["hello"]


def test_remove_handler():
    hook = EventHook()
    results = []
    handler = lambda x: results.append(x)
    hook.addHandler(handler)
    hook.removeHandler(handler)
    hook.fire("hello")
    assert results == []


def test_fire_multiple_handlers():
    hook = EventHook()
    results = []
    hook.addHandler(lambda: results.append("a"))
    hook.addHandler(lambda: results.append("b"))
    hook.fire()
    assert results == ["a", "b"]


def test_fire_with_kwargs():
    hook = EventHook()
    results = []
    hook.addHandler(lambda key=None: results.append(key))
    hook.fire(key="val")
    assert results == ["val"]
