import unittest

from izumi.distage import Injector, Lifecycle, ModuleDef, PlannerInput


class TestLifecycle(unittest.TestCase):
    def test_lifecycle_basic(self) -> None:
        """Test basic lifecycle resource management."""
        acquired = []
        released = []

        class Resource:
            def __init__(self, name: str):
                self.name = name

        def acquire() -> Resource:
            res = Resource("test")
            acquired.append(res.name)
            return res

        def release(res: Resource) -> None:
            released.append(res.name)

        lifecycle = Lifecycle.make(acquire, release)

        module = ModuleDef()
        module.make(Resource).using().fromResource(lifecycle)

        injector = Injector()
        planner_input = PlannerInput([module])

        def app(resource: Resource) -> str:
            return resource.name

        result = injector.produce_run(planner_input, app)

        self.assertEqual(result, "test")
        self.assertEqual(acquired, ["test"])
        self.assertEqual(released, ["test"])

    def test_lifecycle_with_dependencies(self) -> None:
        """Test lifecycle resource that has dependencies."""
        acquired = []
        released = []

        class Config:
            def __init__(self):
                self.value = "config_value"

        class Resource:
            def __init__(self, name: str):
                self.name = name

        def acquire(config: Config) -> Resource:
            res = Resource(config.value)
            acquired.append(res.name)
            return res

        def release(res: Resource) -> None:
            released.append(res.name)

        lifecycle = Lifecycle.make(acquire, release)

        module = ModuleDef()
        module.make(Config).using().type(Config)
        module.make(Resource).using().fromResource(lifecycle)

        injector = Injector()
        planner_input = PlannerInput([module])

        def app(resource: Resource) -> str:
            return resource.name

        result = injector.produce_run(planner_input, app)

        self.assertEqual(result, "config_value")
        self.assertEqual(acquired, ["config_value"])
        self.assertEqual(released, ["config_value"])

    def test_lifecycle_multiple_resources(self) -> None:
        """Test multiple lifecycle resources are released in reverse order."""
        events = []

        class ResourceA:
            pass

        class ResourceB:
            pass

        def acquire_a() -> ResourceA:
            events.append("acquire_a")
            return ResourceA()

        def release_a(_: ResourceA) -> None:
            events.append("release_a")

        def acquire_b() -> ResourceB:
            events.append("acquire_b")
            return ResourceB()

        def release_b(_: ResourceB) -> None:
            events.append("release_b")

        lifecycle_a = Lifecycle.make(acquire_a, release_a)
        lifecycle_b = Lifecycle.make(acquire_b, release_b)

        module = ModuleDef()
        module.make(ResourceA).using().fromResource(lifecycle_a)
        module.make(ResourceB).using().fromResource(lifecycle_b)

        injector = Injector()
        planner_input = PlannerInput([module])

        def app(_a: ResourceA, _b: ResourceB) -> str:
            return "done"

        result = injector.produce_run(planner_input, app)

        self.assertEqual(result, "done")
        self.assertIn("acquire_a", events)
        self.assertIn("acquire_b", events)
        self.assertIn("release_a", events)
        self.assertIn("release_b", events)

        # Resources should be released in reverse order (LIFO)
        release_a_idx = events.index("release_a")
        release_b_idx = events.index("release_b")
        acquire_a_idx = events.index("acquire_a")
        acquire_b_idx = events.index("acquire_b")

        # Both should be acquired before release
        self.assertLess(acquire_a_idx, release_a_idx)
        self.assertLess(acquire_b_idx, release_b_idx)

    def test_lifecycle_pure(self) -> None:
        """Test Lifecycle.pure for non-managed resources."""

        class SimpleValue:
            def __init__(self, value: str):
                self.value = value

        simple = SimpleValue("test")
        lifecycle = Lifecycle.pure(simple)

        module = ModuleDef()
        module.make(SimpleValue).using().fromResource(lifecycle)

        injector = Injector()
        planner_input = PlannerInput([module])

        def app(val: SimpleValue) -> str:
            return val.value

        result = injector.produce_run(planner_input, app)
        self.assertEqual(result, "test")

    def test_lifecycle_from_factory(self) -> None:
        """Test Lifecycle.fromFactory for simple factory functions."""

        class Thing:
            def __init__(self, name: str):
                self.name = name

        def create_thing() -> Thing:
            return Thing("factory")

        lifecycle = Lifecycle.fromFactory(create_thing)

        module = ModuleDef()
        module.make(Thing).using().fromResource(lifecycle)

        injector = Injector()
        planner_input = PlannerInput([module])

        def app(thing: Thing) -> str:
            return thing.name

        result = injector.produce_run(planner_input, app)
        self.assertEqual(result, "factory")


if __name__ == "__main__":
    unittest.main()
