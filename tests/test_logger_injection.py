#!/usr/bin/env python3
"""
Unit tests for automatic logger injection functionality.
"""

import logging
import unittest
from unittest.mock import patch

from izumi.distage import Injector, ModuleDef, PlannerInput
from izumi.distage.logger_injection import AutoLoggerManager, LoggerLocationIntrospector
from izumi.distage.model import DIKey


class TestLoggerLocationIntrospector(unittest.TestCase):
    """Test logger location introspection."""

    def test_get_logger_location_name_basic(self):
        """Test basic location name extraction."""
        # This test will run from this test method
        location = LoggerLocationIntrospector.get_logger_location_name()

        # Should contain the test class and/or method information
        # The exact format may vary but should contain meaningful location info
        self.assertTrue(len(location) > 0)
        self.assertNotEqual(location, "__unknown__")

    def test_get_logger_location_name_from_function(self):
        """Test location name extraction from a function."""

        def test_function():
            return LoggerLocationIntrospector.get_logger_location_name()

        location = test_function()
        # Should contain meaningful location information
        self.assertTrue(len(location) > 0)
        self.assertNotEqual(location, "__unknown__")

    def test_get_logger_location_name_from_class_method(self):
        """Test location name extraction from a class method."""

        class TestClass:
            def test_method(self):
                return LoggerLocationIntrospector.get_logger_location_name()

        instance = TestClass()
        location = instance.test_method()
        # Should contain meaningful location information
        self.assertTrue(len(location) > 0)
        self.assertNotEqual(location, "__unknown__")

    def test_get_module_name_from_filename(self):
        """Test module name extraction from filename."""
        # Test various filename formats
        self.assertEqual(
            LoggerLocationIntrospector._get_module_name_from_filename("/path/to/module.py"),
            "module",
        )
        self.assertEqual(
            LoggerLocationIntrospector._get_module_name_from_filename(r"C:\path\to\module.py"),
            "module",
        )
        self.assertEqual(
            LoggerLocationIntrospector._get_module_name_from_filename("__main__.py"), "__main__"
        )
        self.assertEqual(
            LoggerLocationIntrospector._get_module_name_from_filename("<stdin>"), "__interactive__"
        )


class TestAutoLoggerManager(unittest.TestCase):
    """Test automatic logger management."""

    def test_should_auto_inject_logger(self):
        """Test logger auto-injection detection."""
        from izumi.distage.model import InstanceKey

        # Should auto-inject for unnamed Logger
        logger_key_unnamed = InstanceKey(logging.Logger, None)
        self.assertTrue(AutoLoggerManager.should_auto_inject_logger(logger_key_unnamed))

        # Should NOT auto-inject for named Logger
        logger_key_named = InstanceKey(logging.Logger, "my-logger")
        self.assertFalse(AutoLoggerManager.should_auto_inject_logger(logger_key_named))

        # Should NOT auto-inject for other types
        str_key = InstanceKey(str, None)
        self.assertFalse(AutoLoggerManager.should_auto_inject_logger(str_key))

    def test_create_logger_factory(self):
        """Test logger factory creation."""
        factory = AutoLoggerManager.create_logger_factory("test.logger")
        logger = factory()

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test.logger")

    def test_create_logger_binding(self):
        """Test logger binding creation."""
        binding = AutoLoggerManager.create_logger_binding("test.location")

        # Check that binding key is correct
        from izumi.distage.model import InstanceKey

        expected_key = InstanceKey(logging.Logger, "__logger__.test.location")
        self.assertEqual(binding.key, expected_key)

        # Check that binding creates the right logger
        from izumi.distage.functoid import Functoid

        self.assertIsInstance(binding.functoid, Functoid)
        # Verify it's a function functoid by checking it has an original_func
        self.assertIsNotNone(binding.functoid.original_func)

    def test_rewrite_logger_key(self):
        """Test logger key rewriting."""
        from izumi.distage.model import InstanceKey

        original_key = InstanceKey(logging.Logger, None)
        rewritten_key = AutoLoggerManager.rewrite_logger_key(original_key, "test.location")

        expected_key = InstanceKey(logging.Logger, "__logger__.test.location")
        self.assertEqual(rewritten_key, expected_key)


class TestAutomaticLoggerInjection(unittest.TestCase):
    """Test automatic logger injection in the DI system."""

    def test_automatic_logger_injection_basic(self):
        """Test basic automatic logger injection."""

        class ServiceWithLogger:
            def __init__(self, logger: logging.Logger):
                self.logger = logger

            def do_something(self) -> str:
                self.logger.info("Doing something")
                return f"Logger name: {self.logger.name}"

        # Create module without explicit logger binding
        module = ModuleDef()
        module.make(ServiceWithLogger).using().type(ServiceWithLogger)

        # Should automatically inject logger
        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithLogger))

        self.assertIsInstance(service.logger, logging.Logger)
        # Logger name should be based on the location where it was requested
        self.assertIsNotNone(service.logger.name)

    def test_automatic_logger_injection_with_named_logger(self):
        """Test that named loggers are not auto-injected."""
        from typing import Annotated

        from izumi.distage import Id

        class ServiceWithNamedLogger:
            def __init__(self, logger: Annotated[logging.Logger, Id("my-logger")]):
                self.logger = logger

        # Create module without explicit logger binding
        module = ModuleDef()
        module.make(ServiceWithNamedLogger).using().type(ServiceWithNamedLogger)

        # Should fail because named logger is not auto-injected
        injector = Injector()
        planner_input = PlannerInput([module])

        with self.assertRaises(Exception) as context:
            injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithNamedLogger))

        self.assertIn("No binding found", str(context.exception))
        self.assertIn("my-logger", str(context.exception))

    def test_automatic_logger_injection_with_explicit_binding(self):
        """Test that explicit logger bindings take precedence."""

        class ServiceWithLogger:
            def __init__(self, logger: logging.Logger):
                self.logger = logger

        # Create explicit logger binding
        explicit_logger = logging.getLogger("explicit-logger")

        module = ModuleDef()
        module.make(ServiceWithLogger).using().type(ServiceWithLogger)
        module.make(logging.Logger).using().value(explicit_logger)

        # Should use explicit binding, not auto-injection
        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithLogger))

        self.assertIs(service.logger, explicit_logger)
        self.assertEqual(service.logger.name, "explicit-logger")

    def test_automatic_logger_injection_in_factory(self):
        """Test automatic logger injection in factory functions."""

        def create_service(logger: logging.Logger) -> str:
            logger.info("Creating service")
            return f"Service with logger: {logger.name}"

        module = ModuleDef()
        module.make(str).using().func(create_service)

        injector = Injector()
        planner_input = PlannerInput([module])
        result = injector.produce(injector.plan(planner_input)).get(DIKey.of(str))

        self.assertIsInstance(result, str)
        self.assertIn("Service with logger:", result)

    def test_automatic_logger_injection_multiple_services(self):
        """Test that different services get loggers with appropriate names."""

        class ServiceA:
            def __init__(self, logger: logging.Logger):
                self.logger = logger

        class ServiceB:
            def __init__(self, logger: logging.Logger):
                self.logger = logger

        module = ModuleDef()
        module.make(ServiceA).using().type(ServiceA)
        module.make(ServiceB).using().type(ServiceB)

        injector = Injector()
        planner_input = PlannerInput([module])

        service_a = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceA))
        service_b = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceB))

        # Both should have loggers
        self.assertIsInstance(service_a.logger, logging.Logger)
        self.assertIsInstance(service_b.logger, logging.Logger)

        # Logger names should be meaningful (not empty)
        self.assertNotEqual(service_a.logger.name, "")
        self.assertNotEqual(service_b.logger.name, "")

    def test_automatic_logger_injection_nested_dependencies(self):
        """Test automatic logger injection with nested dependencies."""

        class DatabaseService:
            def __init__(self, logger: logging.Logger):
                self.logger = logger

        class UserService:
            def __init__(self, database: DatabaseService, logger: logging.Logger):
                self.database = database
                self.logger = logger

        module = ModuleDef()
        module.make(DatabaseService).using().type(DatabaseService)
        module.make(UserService).using().type(UserService)

        injector = Injector()
        planner_input = PlannerInput([module])
        user_service = injector.produce(injector.plan(planner_input)).get(DIKey.of(UserService))

        # Both services should have loggers
        self.assertIsInstance(user_service.logger, logging.Logger)
        self.assertIsInstance(user_service.database.logger, logging.Logger)

    @patch("logging.getLogger")
    def test_logger_names_are_meaningful(self, mock_get_logger):
        """Test that auto-injected loggers get meaningful names."""
        mock_logger = logging.Logger("test")
        mock_get_logger.return_value = mock_logger

        class TestService:
            def __init__(self, logger: logging.Logger):
                self.logger = logger

        module = ModuleDef()
        module.make(TestService).using().type(TestService)

        injector = Injector()
        planner_input = PlannerInput([module])
        injector.produce(injector.plan(planner_input)).get(DIKey.of(TestService))

        # Should have called getLogger with a meaningful name
        mock_get_logger.assert_called()
        call_args = mock_get_logger.call_args[0]
        self.assertTrue(len(call_args) > 0)
        logger_name = call_args[0]

        # Logger name should contain module information
        self.assertIsInstance(logger_name, str)
        self.assertNotEqual(logger_name, "")

    def test_produce_run_with_automatic_logger(self):
        """Test automatic logger injection with produce_run."""

        def business_logic(logger: logging.Logger) -> str:
            logger.info("Running business logic")
            return f"Business logic executed with logger: {logger.name}"

        module = ModuleDef()  # Empty module

        injector = Injector()
        planner_input = PlannerInput([module])
        result = injector.produce_run(planner_input, business_logic)

        self.assertIsInstance(result, str)
        self.assertIn("Business logic executed with logger:", result)


if __name__ == "__main__":
    unittest.main()
