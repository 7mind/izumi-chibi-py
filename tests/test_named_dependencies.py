#!/usr/bin/env python3
"""
Unit tests for named dependency injection using Id annotations.
"""

import unittest
from dataclasses import dataclass
from typing import Annotated

from izumi.distage import Id, Injector, ModuleDef, PlannerInput


class TestNamedDependencies(unittest.TestCase):
    """Test named dependency injection functionality."""

    def test_id_annotation_basic(self):
        """Test basic Id annotation creation."""
        id_annotation = Id("test-id")
        self.assertEqual(id_annotation.value, "test-id")
        self.assertEqual(repr(id_annotation), "Id('test-id')")

    def test_id_annotation_equality(self):
        """Test Id annotation equality."""
        id1 = Id("same")
        id2 = Id("same")
        id3 = Id("different")

        self.assertEqual(id1, id2)
        self.assertNotEqual(id1, id3)
        self.assertEqual(hash(id1), hash(id2))
        self.assertNotEqual(hash(id1), hash(id3))

    def test_named_binding_with_module_def(self):
        """Test creating named bindings using ModuleDef."""
        module = ModuleDef()
        module.make(str).named("primary").using().value("primary-string")
        module.make(str).named("secondary").using().value("secondary-string")

        injector = Injector()
        planner_input = PlannerInput([module])

        primary = injector.produce(injector.plan(planner_input)).get(str, "primary")
        secondary = injector.produce(injector.plan(planner_input)).get(str, "secondary")

        self.assertEqual(primary, "primary-string")
        self.assertEqual(secondary, "secondary-string")

    def test_annotated_constructor_injection(self):
        """Test constructor injection with Annotated types."""

        class DatabaseService:
            def __init__(
                self, host: Annotated[str, Id("db-host")], port: Annotated[int, Id("db-port")]
            ):
                self.host = host
                self.port = port

        module = ModuleDef()
        module.make(str).named("db-host").using().value("localhost")
        module.make(int).named("db-port").using().value(5432)
        module.make(DatabaseService).using().type(DatabaseService)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DatabaseService)

        self.assertEqual(service.host, "localhost")
        self.assertEqual(service.port, 5432)

    def test_annotated_function_injection(self):
        """Test function injection with Annotated types."""

        def create_connection_string(
            host: Annotated[str, Id("db-host")],
            port: Annotated[int, Id("db-port")],
            database: Annotated[str, Id("db-name")],
        ) -> str:
            return f"postgresql://{host}:{port}/{database}"

        module = ModuleDef()
        module.make(str).named("db-host").using().value("localhost")
        module.make(int).named("db-port").using().value(5432)
        module.make(str).named("db-name").using().value("myapp")
        module.make(str).named("connection").using().func(create_connection_string)

        injector = Injector()
        planner_input = PlannerInput([module])
        connection_string = injector.produce(injector.plan(planner_input)).get(str, "connection")

        self.assertEqual(connection_string, "postgresql://localhost:5432/myapp")

    def test_annotated_dataclass_injection(self):
        """Test dataclass injection with Annotated types."""

        @dataclass
        class Config:
            host: Annotated[str, Id("server-host")]
            port: Annotated[int, Id("server-port")]
            debug: bool = False

        module = ModuleDef()
        module.make(str).named("server-host").using().value("0.0.0.0")
        module.make(int).named("server-port").using().value(8080)
        module.make(Config).using().type(Config)

        injector = Injector()
        planner_input = PlannerInput([module])
        config = injector.produce(injector.plan(planner_input)).get(Config)

        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 8080)
        self.assertEqual(config.debug, False)  # Default value

    def test_mixed_named_and_unnamed_dependencies(self):
        """Test mixing named and unnamed dependencies."""

        class Logger:
            def __init__(self, name: str):
                self.name = name

        class Service:
            def __init__(
                self,
                logger: Logger,
                api_key: Annotated[str, Id("api-key")],
                timeout: Annotated[int, Id("timeout")],
            ):
                self.logger = logger
                self.api_key = api_key
                self.timeout = timeout

        module = ModuleDef()
        module.make(Logger).using().value(Logger("default-logger"))
        module.make(str).named("api-key").using().value("secret-key-123")
        module.make(int).named("timeout").using().value(30)
        module.make(Service).using().type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(Service)

        self.assertEqual(service.logger.name, "default-logger")
        self.assertEqual(service.api_key, "secret-key-123")
        self.assertEqual(service.timeout, 30)

    def test_produce_run_with_named_dependencies(self):
        """Test produce_run with named dependencies."""

        def my_application(
            database_url: Annotated[str, Id("db-url")],
            redis_url: Annotated[str, Id("redis-url")],
            app_name: str,  # Unnamed dependency
        ) -> str:
            return f"App '{app_name}' connecting to DB: {database_url}, Redis: {redis_url}"

        module = ModuleDef()
        module.make(str).named("db-url").using().value("postgresql://localhost/app")
        module.make(str).named("redis-url").using().value("redis://localhost:6379")
        module.make(str).using().value("MyApplication")  # Unnamed binding

        injector = Injector()
        planner_input = PlannerInput([module])
        result = injector.produce_run(planner_input, my_application)

        expected = "App 'MyApplication' connecting to DB: postgresql://localhost/app, Redis: redis://localhost:6379"
        self.assertEqual(result, expected)

    def test_locator_run_with_named_dependencies(self):
        """Test Locator.run with named dependencies."""

        def worker_function(
            worker_id: Annotated[str, Id("worker-id")], batch_size: Annotated[int, Id("batch-size")]
        ) -> str:
            return f"Worker {worker_id} processing {batch_size} items"

        module = ModuleDef()
        module.make(str).named("worker-id").using().value("worker-001")
        module.make(int).named("batch-size").using().value(100)

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)
        locator = injector.produce(plan)

        result = locator.run(worker_function)
        self.assertEqual(result, "Worker worker-001 processing 100 items")

    def test_error_on_missing_named_dependency(self):
        """Test error when a named dependency is missing."""

        class Service:
            def __init__(self, config: Annotated[str, Id("missing-config")]):
                self.config = config

        module = ModuleDef()
        module.make(Service).using().type(Service)
        # Note: not binding the "missing-config" name

        injector = Injector()
        planner_input = PlannerInput([module])

        from izumi.distage.model.graph import MissingBindingError

        with self.assertRaises(MissingBindingError) as cm:
            injector.produce(injector.plan(planner_input)).get(Service)

        error_message = str(cm.exception)
        self.assertIn("No binding found", error_message)
        self.assertIn("missing-config", error_message)

    def test_optional_named_dependency(self):
        """Test optional named dependencies with defaults."""

        class Service:
            def __init__(
                self,
                required: Annotated[str, Id("required")],
                optional: Annotated[str, Id("optional")] = "default",
            ):
                self.required = required
                self.optional = optional

        module = ModuleDef()
        module.make(str).named("required").using().value("required-value")
        # Note: not binding "optional" - should use default
        module.make(Service).using().type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(Service)

        self.assertEqual(service.required, "required-value")
        self.assertEqual(service.optional, "default")

    def test_complex_nested_named_dependencies(self):
        """Test complex scenario with nested named dependencies."""

        class Database:
            def __init__(self, url: Annotated[str, Id("db-url")]):
                self.url = url

        class Cache:
            def __init__(self, url: Annotated[str, Id("cache-url")]):
                self.url = url

        class UserService:
            def __init__(self, database: Database, cache: Cache):
                self.database = database
                self.cache = cache

        class Application:
            def __init__(
                self,
                user_service: UserService,
                app_name: Annotated[str, Id("app-name")],
                version: Annotated[str, Id("app-version")],
            ):
                self.user_service = user_service
                self.app_name = app_name
                self.version = version

        module = ModuleDef()
        module.make(str).named("db-url").using().value("postgresql://localhost/users")
        module.make(str).named("cache-url").using().value("redis://localhost:6379")
        module.make(str).named("app-name").using().value("UserApp")
        module.make(str).named("app-version").using().value("1.0.0")
        module.make(Database).using().type(Database)
        module.make(Cache).using().type(Cache)
        module.make(UserService).using().type(UserService)
        module.make(Application).using().type(Application)

        injector = Injector()
        planner_input = PlannerInput([module])
        app = injector.produce(injector.plan(planner_input)).get(Application)

        self.assertEqual(app.app_name, "UserApp")
        self.assertEqual(app.version, "1.0.0")
        self.assertEqual(app.user_service.database.url, "postgresql://localhost/users")
        self.assertEqual(app.user_service.cache.url, "redis://localhost:6379")

    def test_lambda_factory_with_named_dependencies(self):
        """Test lambda factory functions with named dependencies."""

        module = ModuleDef()
        module.make(str).named("prefix").using().value("LOG")
        module.make(str).named("level").using().value("INFO")

        # Factory function that uses named dependencies
        def create_log_format(
            prefix: Annotated[str, Id("prefix")], level: Annotated[str, Id("level")]
        ) -> str:
            return f"[{prefix}:{level}]"

        module.make(str).named("log-format").using().func(create_log_format)

        injector = Injector()
        planner_input = PlannerInput([module])
        log_format = injector.produce(injector.plan(planner_input)).get(str, "log-format")

        self.assertEqual(log_format, "[LOG:INFO]")


if __name__ == "__main__":
    unittest.main()
