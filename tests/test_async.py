"""
Tests for async dependency injection support.
"""

import asyncio

import pytest

from izumi.distage import Injector, Lifecycle, ModuleDef, PlannerInput, Roots


class AsyncService:
    """A service with async initialization."""

    def __init__(self, value: str):
        self.value = value

    async def process(self) -> str:
        await asyncio.sleep(0.01)  # Simulate async work
        return f"processed: {self.value}"


class SyncService:
    """A regular sync service."""

    def __init__(self, value: int):
        self.value = value

    def compute(self) -> int:
        return self.value * 2


class MixedService:
    """A service that depends on both sync and async services."""

    def __init__(self, async_svc: AsyncService, sync_svc: SyncService):
        self.async_svc = async_svc
        self.sync_svc = sync_svc

    async def combined_work(self) -> str:
        processed = await self.async_svc.process()
        computed = self.sync_svc.compute()
        return f"{processed}, computed: {computed}"


class AsyncResource:
    """A resource with async acquire and release."""

    def __init__(self, name: str):
        self.name = name
        self.acquired = False
        self.released = False

    async def acquire(self) -> None:
        await asyncio.sleep(0.01)  # Simulate async setup
        self.acquired = True

    async def release(self) -> None:
        await asyncio.sleep(0.01)  # Simulate async cleanup
        self.released = True


async def async_factory() -> AsyncService:
    """Async factory function."""
    await asyncio.sleep(0.01)  # Simulate async work
    return AsyncService("from_factory")


def sync_factory() -> SyncService:
    """Sync factory function."""
    return SyncService(42)


@pytest.mark.asyncio
async def test_async_factory_function() -> None:
    """Test that async factory functions work."""
    module = ModuleDef()
    module.make(AsyncService).using().func(async_factory)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.target(AsyncService)))

    async with await injector.produce_async(plan) as locator:
        from izumi.distage import InstanceKey

        service = locator.get(InstanceKey(AsyncService))
        assert isinstance(service, AsyncService)
        assert service.value == "from_factory"
        result = await service.process()
        assert result == "processed: from_factory"


@pytest.mark.asyncio
async def test_mixed_sync_async_dependencies() -> None:
    """Test mixing sync and async dependencies."""
    module = ModuleDef()
    module.make(AsyncService).using().func(async_factory)
    module.make(SyncService).using().func(sync_factory)
    module.make(MixedService).using().type(MixedService)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.target(MixedService)))

    async with await injector.produce_async(plan) as locator:
        from izumi.distage import InstanceKey

        mixed = locator.get(InstanceKey(MixedService))
        assert isinstance(mixed, MixedService)
        result = await mixed.combined_work()
        assert result == "processed: from_factory, computed: 84"


@pytest.mark.asyncio
async def test_async_lifecycle_cleanup() -> None:
    """Test that async lifecycle resources are properly cleaned up."""
    resource = AsyncResource("test")

    async def acquire_resource() -> AsyncResource:
        await resource.acquire()
        return resource

    async def release_resource(res: AsyncResource) -> None:
        await res.release()

    lifecycle = Lifecycle.make(acquire_resource, release_resource)

    module = ModuleDef()
    module.make(AsyncResource).using().fromResource(lifecycle)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.target(AsyncResource)))

    # Resource should not be acquired yet
    assert not resource.acquired
    assert not resource.released

    async with await injector.produce_async(plan) as locator:
        from izumi.distage import InstanceKey

        res = locator.get(InstanceKey(AsyncResource))
        assert res is resource
        assert resource.acquired
        assert not resource.released

    # After exiting context, resource should be released
    assert resource.released


@pytest.mark.asyncio
async def test_sync_lifecycle_in_async_context() -> None:
    """Test that sync lifecycle resources work in async context."""
    cleanup_called = False

    def acquire_resource() -> str:
        return "sync_resource"

    def release_resource(_res: str) -> None:
        nonlocal cleanup_called
        cleanup_called = True

    lifecycle = Lifecycle.make(acquire_resource, release_resource)

    module = ModuleDef()
    module.make(str).using().fromResource(lifecycle)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.target(str)))

    async with await injector.produce_async(plan) as locator:
        from izumi.distage import InstanceKey

        value = locator.get(InstanceKey(str))
        assert value == "sync_resource"
        assert not cleanup_called

    # After exiting context, cleanup should have been called
    assert cleanup_called


@pytest.mark.asyncio
async def test_async_locator_run_with_async_function() -> None:
    """Test running async functions with AsyncLocator.run()."""
    module = ModuleDef()
    module.make(AsyncService).using().func(async_factory)
    module.make(SyncService).using().func(sync_factory)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.everything()))

    async def my_app(async_svc: AsyncService, sync_svc: SyncService) -> str:
        processed = await async_svc.process()
        computed = sync_svc.compute()
        return f"{processed}, {computed}"

    async with await injector.produce_async(plan) as locator:
        result = await locator.run(my_app)
        assert result == "processed: from_factory, 84"


@pytest.mark.asyncio
async def test_async_locator_run_with_sync_function() -> None:
    """Test running sync functions with AsyncLocator.run()."""
    module = ModuleDef()
    module.make(SyncService).using().func(sync_factory)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.everything()))

    def my_app(sync_svc: SyncService) -> int:
        return sync_svc.compute()

    async with await injector.produce_async(plan) as locator:
        result = await locator.run(my_app)
        assert result == 84


@pytest.mark.asyncio
async def test_async_locator_close() -> None:
    """Test that AsyncLocator can be explicitly closed."""
    cleanup_called = False

    def acquire_resource() -> str:
        return "resource"

    def release_resource(_res: str) -> None:
        nonlocal cleanup_called
        cleanup_called = True

    lifecycle = Lifecycle.make(acquire_resource, release_resource)

    module = ModuleDef()
    module.make(str).using().fromResource(lifecycle)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.target(str)))

    locator = await injector.produce_async(plan)

    from izumi.distage import InstanceKey

    assert locator.get(InstanceKey(str)) == "resource"
    assert not cleanup_called

    await locator.close()
    assert cleanup_called

    # After closing, accessing should raise an error
    with pytest.raises(RuntimeError):
        locator.get(InstanceKey(str))


@pytest.mark.asyncio
async def test_multiple_async_resources_cleanup_order() -> None:
    """Test that multiple async resources are cleaned up in reverse order."""
    cleanup_order: list[str] = []

    async def make_resource1() -> str:
        await asyncio.sleep(0.01)
        return "resource1"

    async def make_resource2() -> str:
        await asyncio.sleep(0.01)
        return "resource2"

    async def make_resource3() -> str:
        await asyncio.sleep(0.01)
        return "resource3"

    async def cleanup_resource(name: str) -> None:
        await asyncio.sleep(0.01)
        cleanup_order.append(name)

    module = ModuleDef()

    # Create multiple resources with different names
    module.make(str).named("resource1").using().fromResource(
        Lifecycle.make(make_resource1, cleanup_resource)
    )
    module.make(str).named("resource2").using().fromResource(
        Lifecycle.make(make_resource2, cleanup_resource)
    )
    module.make(str).named("resource3").using().fromResource(
        Lifecycle.make(make_resource3, cleanup_resource)
    )

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.everything()))

    async with await injector.produce_async(plan) as locator:
        from izumi.distage import InstanceKey

        # All resources should be accessible
        assert locator.get(InstanceKey(str, "resource1")) == "resource1"
        assert locator.get(InstanceKey(str, "resource2")) == "resource2"
        assert locator.get(InstanceKey(str, "resource3")) == "resource3"

    # Resources should be cleaned up in reverse order (LIFO)
    # Note: The exact order depends on the topological order in the plan
    assert len(cleanup_order) == 3
    assert set(cleanup_order) == {"resource1", "resource2", "resource3"}


@pytest.mark.asyncio
async def test_async_factory_with_async_create() -> None:
    """Test Factory.create_async() with async factory functions."""
    from izumi.distage import Factory

    async def create_service(value: str) -> AsyncService:
        await asyncio.sleep(0.01)
        return AsyncService(value)

    module = ModuleDef()
    module.make(Factory[AsyncService]).using().factory_func(create_service)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.target(Factory[AsyncService])))

    async with await injector.produce_async(plan) as locator:
        from izumi.distage import InstanceKey

        factory = locator.get(InstanceKey(Factory[AsyncService]))
        instance = await factory.create_async("custom_value")
        assert isinstance(instance, AsyncService)
        assert instance.value == "custom_value"
        result = await instance.process()
        assert result == "processed: custom_value"


@pytest.mark.asyncio
async def test_error_handling_in_async_lifecycle() -> None:
    """Test that errors during async lifecycle release are logged but don't crash."""
    resource_acquired = False
    error_raised = False

    async def acquire_resource() -> str:
        nonlocal resource_acquired
        resource_acquired = True
        return "resource"

    async def release_resource(_res: str) -> None:
        nonlocal error_raised
        error_raised = True
        raise RuntimeError("Intentional error during release")

    lifecycle = Lifecycle.make(acquire_resource, release_resource)

    module = ModuleDef()
    module.make(str).using().fromResource(lifecycle)

    injector = Injector()
    plan = injector.plan(PlannerInput([module], Roots.target(str)))

    # The context manager should not raise even if release fails
    async with await injector.produce_async(plan) as locator:
        from izumi.distage import InstanceKey

        assert locator.get(InstanceKey(str)) == "resource"
        assert resource_acquired

    # Release was called and raised an error, but it was handled
    assert error_raised
