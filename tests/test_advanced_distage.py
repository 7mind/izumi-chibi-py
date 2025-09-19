#!/usr/bin/env python3
"""
Unit tests for Chibi Izumi advanced features: Roots and Activations.
"""

import unittest

from izumi.distage import Activation, InstanceKey, Injector, ModuleDef, PlannerInput, Roots, StandardAxis
from izumi.distage.activation import Axis, AxisChoiceDef


class TestRoots(unittest.TestCase):
    """Test roots functionality."""

    def test_roots_target(self):
        """Test creating roots for specific target types."""
        roots = Roots.target(str, int)
        self.assertEqual(len(roots.keys), 2)
        self.assertEqual(roots.keys[0].target_type, str)
        self.assertEqual(roots.keys[1].target_type, int)

    def test_roots_everything(self):
        """Test everything roots."""
        roots = Roots.everything()
        self.assertTrue(roots.is_everything())
        self.assertEqual(len(roots.keys), 0)

    def test_roots_empty(self):
        """Test empty roots."""
        roots = Roots.empty()
        self.assertFalse(roots.is_everything())
        self.assertEqual(len(roots.keys), 0)

    def test_roots_addition(self):
        """Test combining roots."""
        roots1 = Roots.target(str)
        roots2 = Roots.target(int)
        combined = roots1 + roots2

        self.assertEqual(len(combined.keys), 2)
        self.assertIn(InstanceKey.get(str), combined.keys)
        self.assertIn(InstanceKey.get(int), combined.keys)

    def test_everything_roots_dominates(self):
        """Test that everything roots dominates in combination."""
        roots1 = Roots.target(str)
        everything = Roots.everything()
        combined = roots1 + everything

        self.assertTrue(combined.is_everything())


class TestActivations(unittest.TestCase):
    """Test activation functionality."""

    def test_empty_activation(self):
        """Test empty activation."""
        activation = Activation.empty()
        self.assertEqual(len(activation.choices), 0)

    def test_activation_creation(self):
        """Test activation creation with choices."""
        activation = Activation(
            {StandardAxis.Mode: StandardAxis.Mode.Test, StandardAxis.World: StandardAxis.World.Mock}
        )

        self.assertEqual(len(activation.choices), 2)
        self.assertEqual(activation.get_choice(StandardAxis.Mode), StandardAxis.Mode.Test)
        self.assertEqual(activation.get_choice(StandardAxis.World), StandardAxis.World.Mock)

    def test_activation_compatibility(self):
        """Test activation compatibility with tags."""
        activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})

        # Compatible tags
        test_tags = {StandardAxis.Mode.Test}
        self.assertTrue(activation.is_compatible_with_tags(test_tags))

        # Incompatible tags
        prod_tags = {StandardAxis.Mode.Prod}
        self.assertFalse(activation.is_compatible_with_tags(prod_tags))

        # Empty tags (should always be compatible)
        empty_tags = set()
        self.assertTrue(activation.is_compatible_with_tags(empty_tags))


class TestRootsAndActivations(unittest.TestCase):
    """Test roots and activations working together."""

    def setUp(self):
        """Set up test fixtures."""

        class Database:
            def query(self, sql: str) -> str:
                return f"DB: {sql}"

        class ProdDatabase(Database):
            def query(self, sql: str) -> str:
                return f"ProdDB: {sql}"

        class TestDatabase(Database):
            def query(self, sql: str) -> str:
                return f"TestDB: {sql}"

        class Service:
            def __init__(self, database: Database):
                self.database = database

            def process(self) -> str:
                return self.database.query("SELECT * FROM table")

        class UnusedService:
            def __init__(self):
                pass

        self.Database = Database
        self.ProdDatabase = ProdDatabase
        self.TestDatabase = TestDatabase
        self.Service = Service
        self.UnusedService = UnusedService

    def test_activation_filtering(self):
        """Test that activations properly filter bindings."""
        module = ModuleDef()
        module.make(self.Database).tagged(StandardAxis.Mode.Prod).using().type(self.ProdDatabase)
        module.make(self.Database).tagged(StandardAxis.Mode.Test).using().type(self.TestDatabase)
        module.make(self.Database).using().type(self.Database)  # Fallback binding
        module.make(self.Service).using().type(self.Service)

        # Test production activation
        prod_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Prod})
        injector = Injector()
        planner_input = PlannerInput([module], activation=prod_activation)
        service = injector.produce(injector.plan(planner_input)).get(self.Service)

        result = service.process()
        self.assertIn("ProdDB", result)

        # Test testing activation
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_activation)
        service = injector.produce(injector.plan(planner_input)).get(self.Service)

        result = service.process()
        self.assertIn("TestDB", result)

    def test_roots_garbage_collection(self):
        """Test that roots perform garbage collection."""
        module = ModuleDef()
        module.make(self.Database).using().type(self.Database)
        module.make(self.Service).using().type(self.Service)
        module.make(self.UnusedService).using().type(self.UnusedService)

        # With specific roots, UnusedService should not be available
        service_roots = Roots.target(self.Service)
        injector = Injector()
        planner_input = PlannerInput([module], roots=service_roots)

        # Service should be available
        service = injector.produce(injector.plan(planner_input)).get(self.Service)
        self.assertIsInstance(service, self.Service)

        # UnusedService should not be available (binding was garbage collected)
        with self.assertRaises(ValueError):
            injector.produce(injector.plan(planner_input)).get(self.UnusedService)

    def test_everything_roots_no_garbage_collection(self):
        """Test that everything roots prevent garbage collection."""
        module = ModuleDef()
        module.make(self.Database).using().type(self.Database)
        module.make(self.Service).using().type(self.Service)
        module.make(self.UnusedService).using().type(self.UnusedService)

        # With everything roots, all services should be available
        injector = Injector()
        planner_input = PlannerInput([module], roots=Roots.everything())

        service = injector.produce(injector.plan(planner_input)).get(self.Service)
        unused = injector.produce(injector.plan(planner_input)).get(self.UnusedService)

        self.assertIsInstance(service, self.Service)
        self.assertIsInstance(unused, self.UnusedService)

    def test_multiple_roots(self):
        """Test using multiple roots."""
        module = ModuleDef()
        module.make(self.Database).using().type(self.Database)
        module.make(self.Service).using().type(self.Service)
        module.make(self.UnusedService).using().type(self.UnusedService)

        # Multiple roots should keep both Service and UnusedService
        multi_roots = Roots.target(self.Service, self.UnusedService)
        injector = Injector()
        planner_input = PlannerInput([module], roots=multi_roots)

        service = injector.produce(injector.plan(planner_input)).get(self.Service)
        unused = injector.produce(injector.plan(planner_input)).get(self.UnusedService)

        self.assertIsInstance(service, self.Service)
        self.assertIsInstance(unused, self.UnusedService)

    def test_roots_and_activations_combined(self):
        """Test roots and activations working together."""
        module = ModuleDef()
        module.make(self.Database).tagged(StandardAxis.Mode.Prod).using().type(self.ProdDatabase)
        module.make(self.Database).tagged(StandardAxis.Mode.Test).using().type(self.TestDatabase)
        module.make(self.Database).using().type(self.Database)  # Fallback binding
        module.make(self.Service).using().type(self.Service)
        module.make(self.UnusedService).using().type(self.UnusedService)

        # Use specific roots with activation
        service_roots = Roots.target(self.Service)
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})

        injector = Injector()
        planner_input = PlannerInput([module], roots=service_roots, activation=test_activation)

        service = injector.produce(injector.plan(planner_input)).get(self.Service)
        result = service.process()

        # Should use TestDatabase due to activation
        self.assertIn("TestDB", result)

        # UnusedService should not be available due to roots
        with self.assertRaises(ValueError):
            injector.produce(injector.plan(planner_input)).get(self.UnusedService)


class TestCustomActivationAxis(unittest.TestCase):
    """Test custom activation axes."""

    def test_custom_axis(self):
        """Test creating and using custom activation axes."""

        # Define custom axis
        class Priority(Axis):
            class High(AxisChoiceDef):
                def __init__(self):
                    super().__init__("High")

            class Low(AxisChoiceDef):
                def __init__(self):
                    super().__init__("Low")

            High = High()
            Low = Low()

        class Service:
            def __init__(self, name: str):
                self.name = name

        class HighPriorityService(Service):
            def __init__(self):
                super().__init__("high")

        class LowPriorityService(Service):
            def __init__(self):
                super().__init__("low")

        module = ModuleDef()
        module.make(Service).tagged(Priority.High).using().type(HighPriorityService)
        module.make(Service).tagged(Priority.Low).using().type(LowPriorityService)
        module.make(Service).using().type(Service)  # Fallback binding

        # Test high priority activation
        high_activation = Activation({Priority: Priority.High})
        injector = Injector()
        planner_input = PlannerInput([module], activation=high_activation)
        service = injector.produce(injector.plan(planner_input)).get(Service)

        self.assertEqual(service.name, "high")

        # Test low priority activation
        low_activation = Activation({Priority: Priority.Low})
        injector = Injector()
        planner_input = PlannerInput([module], activation=low_activation)
        service = injector.produce(injector.plan(planner_input)).get(Service)

        self.assertEqual(service.name, "low")


class TestFallbackBindings(unittest.TestCase):
    """Test fallback binding behavior."""

    def test_untagged_binding_fallback(self):
        """Test that untagged bindings act as fallbacks."""

        class Service:
            def __init__(self, name: str):
                self.name = name

        class DefaultService(Service):
            def __init__(self):
                super().__init__("default")

        class TestService(Service):
            def __init__(self):
                super().__init__("test")

        module = ModuleDef()
        module.make(Service).using().type(DefaultService)  # Untagged fallback
        module.make(Service).tagged(StandardAxis.Mode.Test).using().type(TestService)

        # With test activation, should use TestService
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_activation)
        service = injector.produce(injector.plan(planner_input)).get(Service)
        self.assertEqual(service.name, "test")

        # With prod activation (no matching binding), should use fallback
        prod_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Prod})
        injector = Injector()
        planner_input = PlannerInput([module], activation=prod_activation)
        service = injector.produce(injector.plan(planner_input)).get(Service)
        self.assertEqual(service.name, "default")


if __name__ == "__main__":
    unittest.main()
