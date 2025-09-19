#!/usr/bin/env python3
"""
Unit tests for Factory[T] bindings and assisted injection functionality.
"""

import unittest
from typing import Annotated

from izumi.distage import Factory, Id, Injector, ModuleDef, PlannerInput


class TestFactoryBindings(unittest.TestCase):
    """Test Factory[T] bindings and assisted injection."""

    def test_basic_factory_binding(self):
        """Test basic Factory[T] binding without missing dependencies."""

        class Service:
            def __init__(self):
                self.created_at = "test"

            def get_info(self) -> str:
                return f"Service created at: {self.created_at}"

        module = ModuleDef()
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        # Test that we get a Factory instance
        self.assertIsInstance(factory, Factory)

        # Test creating instances
        instance1 = factory.create()
        instance2 = factory.create()

        # Should be different instances (non-singleton behavior)
        self.assertIsNot(instance1, instance2)
        self.assertIsInstance(instance1, Service)
        self.assertIsInstance(instance2, Service)
        self.assertEqual(instance1.get_info(), "Service created at: test")

    def test_factory_with_resolved_dependencies(self):
        """Test Factory[T] with dependencies that can be resolved from DI."""

        class Config:
            def __init__(self, value: str = "default"):
                self.value = value

        class Service:
            def __init__(self, config: Config):
                self.config = config

            def get_value(self) -> str:
                return self.config.value

        module = ModuleDef()
        module.make(Config).using().value(Config("injected"))
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        instance = factory.create()
        self.assertEqual(instance.get_value(), "injected")

    def test_factory_with_assisted_injection_positional(self):
        """Test Factory[T] with assisted injection via positional arguments."""

        class Config:
            def __init__(self, value: str = "default"):
                self.value = value

        class Service:
            def __init__(self, config: Config, message: str):
                self.config = config
                self.message = message

            def get_info(self) -> str:
                return f"{self.config.value}: {self.message}"

        module = ModuleDef()
        module.make(Config).using().value(Config("from-di"))
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        # The 'message' parameter is not available in DI, so it must be provided
        instance = factory.create("hello world")
        self.assertEqual(instance.get_info(), "from-di: hello world")

    def test_factory_with_assisted_injection_named(self):
        """Test Factory[T] with assisted injection via named arguments."""

        class Config:
            def __init__(self, value: str = "default"):
                self.value = value

        class Service:
            def __init__(self, config: Config, api_key: Annotated[str, Id("api-key")]):
                self.config = config
                self.api_key = api_key

            def get_info(self) -> str:
                return f"{self.config.value} with key: {self.api_key}"

        module = ModuleDef()
        module.make(Config).using().value(Config("from-di"))
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        # The 'api-key' dependency is not available in DI, so it must be provided
        instance = factory.create(**{"api-key": "secret123"})
        self.assertEqual(instance.get_info(), "from-di with key: secret123")

    def test_factory_with_mixed_dependencies(self):
        """Test Factory[T] with both resolved and assisted dependencies."""

        class Database:
            def query(self) -> str:
                return "db-result"

        class Cache:
            def get(self, key: str) -> str:
                return f"cached-{key}"

        class Service:
            def __init__(
                self,
                database: Database,
                user_id: str,
                cache: Cache,
                timeout: Annotated[int, Id("timeout")],
            ):
                self.database = database
                self.user_id = user_id
                self.cache = cache
                self.timeout = timeout

            def process(self) -> str:
                db_result = self.database.query()
                cache_result = self.cache.get(self.user_id)
                return f"{db_result}, {cache_result}, timeout: {self.timeout}"

        module = ModuleDef()
        module.make(Database).using().type(Database)
        module.make(Cache).using().type(Cache)
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        # Database and Cache are resolved from DI
        # user_id (positional) and timeout (named) must be provided
        instance = factory.create("user123", timeout=30)
        result = instance.process()
        self.assertEqual(result, "db-result, cached-user123, timeout: 30")

    def test_factory_missing_required_argument_error(self):
        """Test that Factory[T] raises error when required arguments are missing."""

        class Service:
            def __init__(self, required_param: str):
                self.required_param = required_param

        module = ModuleDef()
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        with self.assertRaises(ValueError) as context:
            factory.create()  # Missing required_param

        self.assertIn("requires 1 positional arguments", str(context.exception))
        self.assertIn("required_param", str(context.exception))

    def test_factory_missing_named_argument_error(self):
        """Test that Factory[T] raises error when required named arguments are missing."""

        class Service:
            def __init__(self, api_key: Annotated[str, Id("api-key")]):
                self.api_key = api_key

        module = ModuleDef()
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        with self.assertRaises(ValueError) as context:
            factory.create()  # Missing api-key

        self.assertIn("requires keyword argument 'api-key'", str(context.exception))

    def test_factory_unexpected_argument_error(self):
        """Test that Factory[T] raises error when unexpected arguments are provided."""

        class Service:
            def __init__(self):
                pass

        module = ModuleDef()
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        with self.assertRaises(TypeError) as context:
            factory.create(unexpected="value")

        self.assertIn("got unexpected keyword arguments: unexpected", str(context.exception))

    def test_factory_with_optional_dependencies(self):
        """Test Factory[T] with optional dependencies using default values."""

        class Config:
            def __init__(self, value: str = "default"):
                self.value = value

        class Service:
            def __init__(self, config: Config, timeout: int = 10):
                self.config = config
                self.timeout = timeout

            def get_info(self) -> str:
                return f"{self.config.value}, timeout: {self.timeout}"

        module = ModuleDef()
        module.make(Config).using().value(Config("from-di"))
        module.make(Factory[Service]).using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Service])

        # Should work with default timeout
        instance = factory.create()
        self.assertEqual(instance.get_info(), "from-di, timeout: 10")

    def test_factory_non_singleton_behavior(self):
        """Test that Factory[T] creates new instances each time (non-singleton)."""

        class Counter:
            count = 0

            def __init__(self):
                Counter.count += 1
                self.instance_id = Counter.count

        module = ModuleDef()
        module.make(Factory[Counter]).using().factory_type(Counter)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[Counter])

        # Reset counter
        Counter.count = 0

        instance1 = factory.create()
        instance2 = factory.create()
        instance3 = factory.create()

        # Each instance should be different
        self.assertIsNot(instance1, instance2)
        self.assertIsNot(instance2, instance3)
        self.assertEqual(instance1.instance_id, 1)
        self.assertEqual(instance2.instance_id, 2)
        self.assertEqual(instance3.instance_id, 3)

    def test_factory_vs_singleton_comparison(self):
        """Test Factory[T] vs regular singleton binding behavior."""

        class Service:
            def __init__(self, value: str = "test"):
                self.value = value

        module = ModuleDef()
        # Regular singleton binding
        module.make(Service).using().type(Service)
        # Factory binding for same type with different name
        module.make(Factory[Service]).named("factory").using().factory_type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])

        # Create a plan and locator to maintain state
        plan = injector.plan(planner_input)
        locator = injector.produce(plan)

        # Get singleton instances from the same locator
        singleton1 = locator.get(Service)
        singleton2 = locator.get(Service)

        # Get factory and create instances
        factory = locator.get(Factory[Service], "factory")
        factory_instance1 = factory.create()
        factory_instance2 = factory.create()

        # Singletons should be the same instance
        self.assertIs(singleton1, singleton2)

        # Factory instances should be different
        self.assertIsNot(factory_instance1, factory_instance2)

        # All should be of the same type
        self.assertIsInstance(singleton1, Service)
        self.assertIsInstance(factory_instance1, Service)
        self.assertIsInstance(factory_instance2, Service)

    def test_factory_with_complex_dependency_graph(self):
        """Test Factory[T] with complex dependency graphs."""

        class DatabaseConfig:
            def __init__(self, url: str = "default://"):
                self.url = url

        class Database:
            def __init__(self, config: DatabaseConfig):
                self.config = config

        class UserRepository:
            def __init__(self, database: Database):
                self.database = database

        class UserService:
            def __init__(self, repository: UserRepository, user_id: str):
                self.repository = repository
                self.user_id = user_id

            def get_info(self) -> str:
                return f"User {self.user_id} on {self.repository.database.config.url}"

        module = ModuleDef()
        module.make(DatabaseConfig).using().value(DatabaseConfig("prod://db"))
        module.make(Database).using().type(Database)
        module.make(UserRepository).using().type(UserRepository)
        module.make(Factory[UserService]).using().factory_type(UserService)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[UserService])

        # Create instances with different user IDs
        user_service1 = factory.create("alice")
        user_service2 = factory.create("bob")

        self.assertEqual(user_service1.get_info(), "User alice on prod://db")
        self.assertEqual(user_service2.get_info(), "User bob on prod://db")

        # Different instances but sharing the same singleton dependencies
        self.assertIsNot(user_service1, user_service2)
        self.assertIs(user_service1.repository, user_service2.repository)  # Singleton


class TestFactoryFunc(unittest.TestCase):
    """Test factory_func binding method."""

    def test_factory_func_binding(self):
        """Test Factory[T] binding with factory function."""

        class Config:
            def __init__(self, value: str = "default"):
                self.value = value

        def create_service(config: Config, message: str) -> str:
            return f"{config.value}: {message}"

        module = ModuleDef()
        module.make(Config).using().value(Config("from-di"))
        module.make(Factory[str]).using().factory_func(create_service)

        injector = Injector()
        planner_input = PlannerInput([module])
        factory = injector.produce(injector.plan(planner_input)).get(Factory[str])

        # Test that we get a Factory instance
        self.assertIsInstance(factory, Factory)

        # The 'message' parameter is not available in DI, so it must be provided
        result = factory.create("hello world")
        self.assertEqual(result, "from-di: hello world")


class TestFactoryRepr(unittest.TestCase):
    """Test Factory[T] string representations."""

    def test_factory_repr(self):
        """Test Factory[T] __repr__ method."""
        from izumi.distage.factory import Factory
        from izumi.distage.functoid import class_functoid

        class MockLocator:
            def get(self, target_type: type, name: str | None = None) -> None:
                pass

        class TestService:
            pass

        functoid = class_functoid(TestService)
        factory = Factory(TestService, MockLocator(), functoid)
        self.assertEqual(repr(factory), "Factory[TestService]")


if __name__ == "__main__":
    unittest.main()
