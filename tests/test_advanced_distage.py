#!/usr/bin/env python3
"""
Unit tests for Chibi Izumi advanced features: Roots and Activations.
"""

import unittest

from izumi.distage import (
    Activation,
    Injector,
    ModuleDef,
    PlannerInput,
    Roots,
    StandardAxis,
)
from izumi.distage.activation import Axis, AxisChoiceDef
from izumi.distage.model import DIKey


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
        self.assertIn(DIKey.of(str), combined.keys)
        self.assertIn(DIKey.of(int), combined.keys)

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
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(self.Service))

        result = service.process()
        self.assertIn("ProdDB", result)

        # Test testing activation
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(self.Service))

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
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(self.Service))
        self.assertIsInstance(service, self.Service)

        # UnusedService should not be available (binding was garbage collected)
        with self.assertRaises(ValueError):
            injector.produce(injector.plan(planner_input)).get(DIKey.of(self.UnusedService))

    def test_everything_roots_no_garbage_collection(self):
        """Test that everything roots prevent garbage collection."""
        module = ModuleDef()
        module.make(self.Database).using().type(self.Database)
        module.make(self.Service).using().type(self.Service)
        module.make(self.UnusedService).using().type(self.UnusedService)

        # With everything roots, all services should be available
        injector = Injector()
        planner_input = PlannerInput([module], roots=Roots.everything())

        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(self.Service))
        unused = injector.produce(injector.plan(planner_input)).get(DIKey.of(self.UnusedService))

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

        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(self.Service))
        unused = injector.produce(injector.plan(planner_input)).get(DIKey.of(self.UnusedService))

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

        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(self.Service))
        result = service.process()

        # Should use TestDatabase due to activation
        self.assertIn("TestDB", result)

        # UnusedService should not be available due to roots
        with self.assertRaises(ValueError):
            injector.produce(injector.plan(planner_input)).get(DIKey.of(self.UnusedService))


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
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

        self.assertEqual(service.name, "high")

        # Test low priority activation
        low_activation = Activation({Priority: Priority.Low})
        injector = Injector()
        planner_input = PlannerInput([module], activation=low_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

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
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))
        self.assertEqual(service.name, "test")

        # With prod activation (no matching binding), should use fallback
        prod_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Prod})
        injector = Injector()
        planner_input = PlannerInput([module], activation=prod_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))
        self.assertEqual(service.name, "default")


class TestAxisTracing(unittest.TestCase):
    """Test path-aware axis tracing functionality."""

    def test_implied_choice_propagation(self):
        """Test that axis choices are propagated through dependency chains."""

        class Database:
            def get_name(self) -> str:
                return "base"

        class TestDB(Database):
            def get_name(self) -> str:
                return "test_db"

        class ProdDB(Database):
            def get_name(self) -> str:
                return "prod_db"

        class Cache:
            def get_name(self) -> str:
                return "base_cache"

        class TestCache(Cache):
            def get_name(self) -> str:
                return "test_cache"

        class ProdCache(Cache):
            def get_name(self) -> str:
                return "prod_cache"

        class Repository:
            def __init__(self, database: Database, cache: Cache):
                self.database = database
                self.cache = cache

        class Service:
            def __init__(self, repository: Repository):
                self.repository = repository

        # Create module with tagged bindings at different levels
        module = ModuleDef()

        # Database bindings
        module.make(Database).tagged(StandardAxis.Mode.Test).using().type(TestDB)
        module.make(Database).tagged(StandardAxis.Mode.Prod).using().type(ProdDB)

        # Cache bindings
        module.make(Cache).tagged(StandardAxis.Mode.Test).using().type(TestCache)
        module.make(Cache).tagged(StandardAxis.Mode.Prod).using().type(ProdCache)

        # Repository and Service (untagged)
        module.make(Repository).using().type(Repository)
        module.make(Service).using().type(Service)

        # Test with Test mode - should propagate to all dependencies
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

        # All dependencies should be Test versions
        self.assertEqual(service.repository.database.get_name(), "test_db")
        self.assertEqual(service.repository.cache.get_name(), "test_cache")

        # Test with Prod mode
        prod_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Prod})
        injector = Injector()
        planner_input = PlannerInput([module], activation=prod_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

        self.assertEqual(service.repository.database.get_name(), "prod_db")
        self.assertEqual(service.repository.cache.get_name(), "prod_cache")

    def test_conflicting_bindings_different_paths(self):
        """Test that different dependency paths can have different axis choices."""

        class DatabaseA:
            def get_mode(self) -> str:
                return "base"

        class TestDatabaseA(DatabaseA):
            def get_mode(self) -> str:
                return "test"

        class ProdDatabaseA(DatabaseA):
            def get_mode(self) -> str:
                return "prod"

        class ServiceA:
            def __init__(self, db: DatabaseA):
                self.db = db

        class DatabaseB:
            def get_mode(self) -> str:
                return "base"

        class TestDatabaseB(DatabaseB):
            def get_mode(self) -> str:
                return "test"

        class ProdDatabaseB(DatabaseB):
            def get_mode(self) -> str:
                return "prod"

        class ServiceB:
            def __init__(self, db: DatabaseB):
                self.db = db

        # Create module with separate service hierarchies
        module = ModuleDef()

        # ServiceA dependencies
        module.make(DatabaseA).tagged(StandardAxis.Mode.Test).using().type(TestDatabaseA)
        module.make(DatabaseA).tagged(StandardAxis.Mode.Prod).using().type(ProdDatabaseA)
        module.make(ServiceA).using().type(ServiceA)

        # ServiceB dependencies
        module.make(DatabaseB).tagged(StandardAxis.Mode.Test).using().type(TestDatabaseB)
        module.make(DatabaseB).tagged(StandardAxis.Mode.Prod).using().type(ProdDatabaseB)
        module.make(ServiceB).using().type(ServiceB)

        # Request both services with Test activation
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput(
            [module], roots=Roots.target(ServiceA, ServiceB), activation=test_activation
        )
        locator = injector.produce(injector.plan(planner_input))

        service_a = locator.get(DIKey.of(ServiceA))
        service_b = locator.get(DIKey.of(ServiceB))

        # Both should use test databases
        self.assertEqual(service_a.db.get_mode(), "test")
        self.assertEqual(service_b.db.get_mode(), "test")

    def test_multiple_axes_interaction(self):
        """Test that multiple axes interact correctly in dependency chains."""

        class Database:
            def get_config(self) -> str:
                return "base"

        class TestRealDB(Database):
            def get_config(self) -> str:
                return "test_real"

        class TestMockDB(Database):
            def get_config(self) -> str:
                return "test_mock"

        class ProdRealDB(Database):
            def get_config(self) -> str:
                return "prod_real"

        class ProdMockDB(Database):
            def get_config(self) -> str:
                return "prod_mock"

        class Service:
            def __init__(self, database: Database):
                self.database = database

        module = ModuleDef()

        # Bindings with multiple axes
        module.make(Database).tagged(StandardAxis.Mode.Test).tagged(
            StandardAxis.World.Real
        ).using().type(TestRealDB)
        module.make(Database).tagged(StandardAxis.Mode.Test).tagged(
            StandardAxis.World.Mock
        ).using().type(TestMockDB)
        module.make(Database).tagged(StandardAxis.Mode.Prod).tagged(
            StandardAxis.World.Real
        ).using().type(ProdRealDB)
        module.make(Database).tagged(StandardAxis.Mode.Prod).tagged(
            StandardAxis.World.Mock
        ).using().type(ProdMockDB)
        module.make(Service).using().type(Service)

        # Test all combinations
        test_cases = [
            (
                {
                    StandardAxis.Mode: StandardAxis.Mode.Test,
                    StandardAxis.World: StandardAxis.World.Real,
                },
                "test_real",
            ),
            (
                {
                    StandardAxis.Mode: StandardAxis.Mode.Test,
                    StandardAxis.World: StandardAxis.World.Mock,
                },
                "test_mock",
            ),
            (
                {
                    StandardAxis.Mode: StandardAxis.Mode.Prod,
                    StandardAxis.World: StandardAxis.World.Real,
                },
                "prod_real",
            ),
            (
                {
                    StandardAxis.Mode: StandardAxis.Mode.Prod,
                    StandardAxis.World: StandardAxis.World.Mock,
                },
                "prod_mock",
            ),
        ]

        for activation_choices, expected_config in test_cases:
            activation = Activation(activation_choices)
            injector = Injector()
            planner_input = PlannerInput([module], activation=activation)
            service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

            self.assertEqual(service.database.get_config(), expected_config)

    def test_deep_dependency_chain_with_tags(self):
        """Test axis choice propagation through deep dependency chains."""

        class Level1:
            def get_level(self) -> str:
                return "1"

        class Level1Test(Level1):
            def get_level(self) -> str:
                return "1_test"

        class Level2:
            def __init__(self, level1: Level1):
                self.level1 = level1

            def get_level(self) -> str:
                return f"2->{self.level1.get_level()}"

        class Level2Test(Level2):
            def get_level(self) -> str:
                return f"2_test->{self.level1.get_level()}"

        class Level3:
            def __init__(self, level2: Level2):
                self.level2 = level2

            def get_level(self) -> str:
                return f"3->{self.level2.get_level()}"

        class Level3Test(Level3):
            def get_level(self) -> str:
                return f"3_test->{self.level2.get_level()}"

        class Level4:
            def __init__(self, level3: Level3):
                self.level3 = level3

            def get_level(self) -> str:
                return f"4->{self.level3.get_level()}"

        module = ModuleDef()

        # Create bindings at each level
        module.make(Level1).tagged(StandardAxis.Mode.Test).using().type(Level1Test)
        module.make(Level1).using().type(Level1)

        module.make(Level2).tagged(StandardAxis.Mode.Test).using().type(Level2Test)
        module.make(Level2).using().type(Level2)

        module.make(Level3).tagged(StandardAxis.Mode.Test).using().type(Level3Test)
        module.make(Level3).using().type(Level3)

        module.make(Level4).using().type(Level4)

        # Test with Test activation
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_activation)
        level4 = injector.produce(injector.plan(planner_input)).get(DIKey.of(Level4))

        result = level4.get_level()
        # Should be: 4->3_test->2_test->1_test
        self.assertIn("4->", result)
        self.assertIn("3_test", result)
        self.assertIn("2_test", result)
        self.assertIn("1_test", result)

    def test_implied_choice_constrains_siblings(self):
        """Test that implied choices from one dependency constrain sibling dependencies."""

        class Logger:
            def get_type(self) -> str:
                return "base"

        class TestLogger(Logger):
            def get_type(self) -> str:
                return "test"

        class ProdLogger(Logger):
            def get_type(self) -> str:
                return "prod"

        class Database:
            def get_type(self) -> str:
                return "base"

        class TestDatabase(Database):
            def get_type(self) -> str:
                return "test"

        class ProdDatabase(Database):
            def get_type(self) -> str:
                return "prod"

        class Service:
            def __init__(self, logger: Logger, database: Database):
                self.logger = logger
                self.database = database

        module = ModuleDef()

        # Logger bindings
        module.make(Logger).tagged(StandardAxis.Mode.Test).using().type(TestLogger)
        module.make(Logger).tagged(StandardAxis.Mode.Prod).using().type(ProdLogger)

        # Database bindings
        module.make(Database).tagged(StandardAxis.Mode.Test).using().type(TestDatabase)
        module.make(Database).tagged(StandardAxis.Mode.Prod).using().type(ProdDatabase)

        # Service
        module.make(Service).using().type(Service)

        # With Test activation, both siblings should be Test versions
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

        self.assertEqual(service.logger.get_type(), "test")
        self.assertEqual(service.database.get_type(), "test")

    def test_untagged_fallback_in_mixed_scenario(self):
        """Test that untagged bindings act as fallbacks when no tagged binding matches."""

        class ComponentA:
            def get_name(self) -> str:
                return "default_a"

        class TestComponentA(ComponentA):
            def get_name(self) -> str:
                return "test_a"

        class ComponentB:
            def get_name(self) -> str:
                return "default_b"

        class Service:
            def __init__(self, a: ComponentA, b: ComponentB):
                self.a = a
                self.b = b

        module = ModuleDef()

        # ComponentA has tagged and untagged bindings
        module.make(ComponentA).tagged(StandardAxis.Mode.Test).using().type(TestComponentA)
        module.make(ComponentA).using().type(ComponentA)

        # ComponentB only has untagged binding
        module.make(ComponentB).using().type(ComponentB)

        module.make(Service).using().type(Service)

        # With Test activation
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

        # ComponentA should use tagged version
        self.assertEqual(service.a.get_name(), "test_a")
        # ComponentB should use untagged fallback
        self.assertEqual(service.b.get_name(), "default_b")

        # With Prod activation (no matching tags)
        prod_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Prod})
        injector = Injector()
        planner_input = PlannerInput([module], activation=prod_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

        # Both should use untagged versions
        self.assertEqual(service.a.get_name(), "default_a")
        self.assertEqual(service.b.get_name(), "default_b")

    def test_specificity_preference_with_multiple_tags(self):
        """Test that more specific bindings (more tags) are preferred."""

        class Service:
            def get_config(self) -> str:
                return "base"

        class TestService(Service):
            def get_config(self) -> str:
                return "test"

        class TestRealService(Service):
            def get_config(self) -> str:
                return "test_real"

        class TestMockService(Service):
            def get_config(self) -> str:
                return "test_mock"

        module = ModuleDef()

        # Bindings with increasing specificity
        module.make(Service).using().type(Service)  # 0 tags
        module.make(Service).tagged(StandardAxis.Mode.Test).using().type(TestService)  # 1 tag
        module.make(Service).tagged(StandardAxis.Mode.Test).tagged(
            StandardAxis.World.Real
        ).using().type(TestRealService)  # 2 tags
        module.make(Service).tagged(StandardAxis.Mode.Test).tagged(
            StandardAxis.World.Mock
        ).using().type(TestMockService)  # 2 tags

        # With just Mode.Test, should prefer most specific binding that matches
        # Since both TestRealService and TestMockService have Mode.Test tags and are valid,
        # the implementation will choose the first one with the most tags
        test_only = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_only)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))
        # Should be one of the 2-tag bindings (TestRealService or TestMockService)
        self.assertIn(service.get_config(), ["test_real", "test_mock"])

        # With Mode.Test + World.Real, should prefer most specific (TestRealService)
        test_real = Activation(
            {StandardAxis.Mode: StandardAxis.Mode.Test, StandardAxis.World: StandardAxis.World.Real}
        )
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_real)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))
        self.assertEqual(service.get_config(), "test_real")

        # With Mode.Test + World.Mock, should prefer TestMockService
        test_mock = Activation(
            {StandardAxis.Mode: StandardAxis.Mode.Test, StandardAxis.World: StandardAxis.World.Mock}
        )
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_mock)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))
        self.assertEqual(service.get_config(), "test_mock")

    def test_no_valid_binding_falls_back_to_untagged(self):
        """Test that when no tagged binding matches, untagged binding is used."""

        class Service:
            def get_name(self) -> str:
                return "default"

        class ProdService(Service):
            def get_name(self) -> str:
                return "prod"

        module = ModuleDef()
        module.make(Service).using().type(Service)  # Untagged fallback
        module.make(Service).tagged(StandardAxis.Mode.Prod).using().type(ProdService)

        # Request with Test activation (no matching tagged binding)
        test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})
        injector = Injector()
        planner_input = PlannerInput([module], activation=test_activation)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

        # Should fall back to untagged
        self.assertEqual(service.get_name(), "default")


if __name__ == "__main__":
    unittest.main()
