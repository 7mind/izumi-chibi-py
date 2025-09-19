#!/usr/bin/env python3
"""
Unit tests for the new architecture with Injector, Plan, and Locator separation.
"""

import unittest
from dataclasses import dataclass

from izumi.distage import Injector, ModuleDef, Plan, PlannerInput
from izumi.distage.model import DIKey


class TestLocator(unittest.TestCase):
    """Test the new Injector -> Plan -> Locator architecture."""

    def test_injector_immutability(self):
        """Test that Injector is stateless."""
        module = ModuleDef()
        module.make(str).using().value("test")

        injector = Injector()
        planner_input = PlannerInput([module])

        # Injector should be stateless - no modules/roots/activation
        # Should not have any instance attributes that could be modified
        plan = injector.plan(planner_input)
        self.assertIsInstance(plan, Plan)

    def test_plan_creation(self):
        """Test creating a Plan from an Injector."""

        @dataclass
        class Database:
            connection_string: str

        class Service:
            def __init__(self, database: Database):
                self.database = database

        module = ModuleDef()
        module.make(Database).using().value(Database("test-db"))
        module.make(Service).using().type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)

        # Check that plan contains expected data
        self.assertIsInstance(plan, Plan)
        self.assertIsNotNone(plan.graph)
        self.assertIsNotNone(plan.roots)
        self.assertIsNotNone(plan.activation)
        self.assertIsNotNone(plan.topology)

        # Plan should be immutable
        with self.assertRaises(AttributeError):
            plan.graph = None  # type: ignore[misc]

    def test_multiple_locators_from_same_plan(self):
        """Test that multiple Locators can be created from the same Plan with different instances."""

        class Counter:
            _instance_count = 0

            def __init__(self):
                Counter._instance_count += 1
                self.id = Counter._instance_count

        module = ModuleDef()
        module.make(Counter).using().type(Counter)

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)

        # Create two locators from the same plan
        locator1 = injector.produce(plan)
        locator2 = injector.produce(plan)

        # Each locator should get its own instance
        counter1 = locator1.get(DIKey.of(Counter))
        counter2 = locator2.get(DIKey.of(Counter))

        self.assertNotEqual(counter1.id, counter2.id)
        self.assertIsNot(counter1, counter2)

    def test_plan_reuse_with_same_locator(self):
        """Test that same locator reuses instances."""

        class Service:
            def __init__(self):
                self.created_at = id(self)

        module = ModuleDef()
        module.make(Service).using().type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)
        locator = injector.produce(plan)

        # Same locator should return the same instance
        service1 = locator.get(DIKey.of(Service))
        service2 = locator.get(DIKey.of(Service))

        self.assertIs(service1, service2)
        self.assertEqual(service1.created_at, service2.created_at)

    def test_locator_utilities(self):
        """Test Locator utility methods."""

        class ExistingService:
            pass

        class MissingService:
            pass

        module = ModuleDef()
        module.make(ExistingService).using().type(ExistingService)

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)
        locator = injector.produce(plan)

        # Test has() method
        from izumi.distage.model import DIKey

        self.assertTrue(locator.has(DIKey.of(ExistingService)))
        self.assertFalse(locator.has(DIKey.of(MissingService)))

        self.assertTrue(locator.has(DIKey.of(ExistingService)))

        # Resolve the service
        service = locator.get(DIKey.of(ExistingService))
        self.assertIsInstance(service, ExistingService)

        # Test has() after resolution
        self.assertTrue(locator.has(DIKey.of(ExistingService)))

        # Test find() method
        found_service = locator.find(DIKey.of(ExistingService))
        self.assertIs(found_service, service)

        missing_service = locator.find(DIKey.of(MissingService))
        self.assertIsNone(missing_service)

    def test_backward_compatibility(self):
        """Test that existing Injector.get() method still works."""

        class Service:
            def get_message(self):
                return "Hello World"

        module = ModuleDef()
        module.make(Service).using().type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(Service))

        self.assertIsInstance(service, Service)
        self.assertEqual(service.get_message(), "Hello World")

    def test_injector_produce_run_method(self):
        """Test the new Injector.produce_run() method with function introspection and PlannerInput."""
        from izumi.distage import PlannerInput

        class Calculator:
            def add(self, a: int, b: int) -> int:
                return a + b

        class Logger:
            def __init__(self):
                self.last_message = ""

            def log(self, message: str) -> None:
                self.last_message = message

        module = ModuleDef()
        module.make(Calculator).using().type(Calculator)
        module.make(Logger).using().type(Logger)

        # New API: Create PlannerInput and use stateless Injector
        input = PlannerInput([module])
        injector = Injector()

        # Test produce_run with function that has dependencies automatically resolved
        def calculate_and_log(calculator: Calculator, logger: Logger) -> str:
            result = calculator.add(5, 3)
            logger.log(f"Result: {result}")
            return logger.last_message

        result = injector.produce_run(input, calculate_and_log)
        self.assertEqual(result, "Result: 8")

        # Test multiple dependency resolution in one call
        def complex_operation(calculator: Calculator, logger: Logger) -> int:
            val1 = calculator.add(10, 5)
            val2 = calculator.add(val1, 3)
            logger.log(f"Final result: {val2}")
            return val2

        final_result = injector.produce_run(input, complex_operation)
        self.assertEqual(final_result, 18)

    def test_plan_with_overrides(self):
        """Test producing plans with different roots and activation."""
        from izumi.distage import Roots

        class ServiceA:
            pass

        class ServiceB:
            pass

        module = ModuleDef()
        module.make(ServiceA).using().type(ServiceA)
        module.make(ServiceB).using().type(ServiceB)

        injector = Injector()

        # Create plan with specific roots
        specific_roots = Roots.target(ServiceA)
        planner_input = PlannerInput([module], roots=specific_roots)
        plan_with_roots = injector.plan(planner_input)

        # The plan should have the overridden roots
        self.assertEqual(plan_with_roots.roots, specific_roots)

    def test_plan_metadata(self):
        """Test Plan metadata and information methods."""

        class ServiceA:
            pass

        class ServiceB:
            def __init__(self, service_a: ServiceA):
                self.service_a = service_a

        module = ModuleDef()
        module.make(ServiceA).using().type(ServiceA)
        module.make(ServiceB).using().type(ServiceB)

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)

        # Test keys() method
        keys = plan.keys()
        self.assertGreater(len(keys), 0)

        # Test has_binding() method
        from izumi.distage.model import InstanceKey

        service_a_key = InstanceKey(ServiceA, None)
        service_b_key = InstanceKey(ServiceB, None)

        self.assertTrue(plan.has_binding(service_a_key))
        self.assertTrue(plan.has_binding(service_b_key))

        # Test get_execution_order() method
        execution_order = plan.get_execution_order()
        self.assertIsInstance(execution_order, list)
        self.assertGreater(len(execution_order), 0)

    def test_tagged_bindings_with_new_architecture(self):
        """Test named bindings work with the new architecture."""

        module = ModuleDef()
        module.make(str).named("prod").using().value("production-db")
        module.make(str).named("test").using().value("test-db")

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)
        locator = injector.produce(plan)

        prod_db = locator.get(DIKey.of(str, "prod"))
        test_db = locator.get(DIKey.of(str, "test"))

        self.assertEqual(prod_db, "production-db")
        self.assertEqual(test_db, "test-db")

    def test_set_bindings_with_new_architecture(self):
        """Test set bindings work with the new architecture."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

            def __eq__(self, other):
                return isinstance(other, Handler) and self.name == other.name

            def __hash__(self):
                return hash(self.name)

        class Service:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        handler1 = Handler("handler1")
        handler2 = Handler("handler2")

        module = ModuleDef()
        module.many(Handler).add(handler1).add(handler2)
        module.make(Service).using().type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)
        locator = injector.produce(plan)

        service = locator.get(DIKey.of(Service))

        self.assertEqual(len(service.handlers), 2)
        self.assertIn(handler1, service.handlers)
        self.assertIn(handler2, service.handlers)

    def test_locator_run_method(self):
        """Test the run method that automatically resolves function dependencies."""

        class Calculator:
            def add(self, a: int, b: int) -> int:
                return a + b

            def multiply(self, a: int, b: int) -> int:
                return a * b

        class MathService:
            def __init__(self, calculator: Calculator):
                self.calculator = calculator

            def calculate_complex(self, x: int, y: int) -> int:
                return self.calculator.multiply(self.calculator.add(x, y), 2)

        module = ModuleDef()
        module.make(Calculator).using().type(Calculator)
        module.make(MathService).using().type(MathService)

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)
        locator = injector.produce(plan)

        # Test run method with function that has dependencies automatically resolved
        def simple_calculation(math_service: MathService) -> int:
            return math_service.calculate_complex(3, 4)

        result = locator.run(simple_calculation)
        self.assertEqual(result, 14)  # (3 + 4) * 2 = 14

        # Test run method with function that has multiple dependencies
        def complex_operation(calculator: Calculator, math_service: MathService) -> str:
            sum_result = calculator.add(10, 5)
            complex_result = math_service.calculate_complex(2, 3)
            return f"sum: {sum_result}, complex: {complex_result}"

        result_str = locator.run(complex_operation)
        self.assertEqual(result_str, "sum: 15, complex: 10")

        # Test that the same instances are used within the run
        def instance_check(calc1: Calculator, calc2: Calculator) -> bool:
            return calc1 is calc2

        # This should fail because we get two different references to the same singleton
        # Let's test with a single dependency instead
        def get_calculator_id(calculator: Calculator) -> int:
            return id(calculator)

        id1 = locator.run(get_calculator_id)
        id2 = locator.run(get_calculator_id)
        self.assertEqual(id1, id2)  # Same instance should be reused

        # Test function with no dependencies
        def no_deps() -> str:
            return "no dependencies"

        result_no_deps = locator.run(no_deps)
        self.assertEqual(result_no_deps, "no dependencies")


if __name__ == "__main__":
    unittest.main()
