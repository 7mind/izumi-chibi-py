#!/usr/bin/env python3
"""
Unit tests for Chibi Izumi library.
"""

import unittest
from dataclasses import dataclass

from izumi.distage import Injector, ModuleDef, PlannerInput
from izumi.distage.graph import CircularDependencyError, MissingBindingError
from izumi.distage.introspection import SignatureIntrospector


class TestBasicBinding(unittest.TestCase):
    """Test basic binding functionality."""

    def test_class_binding(self):
        """Test binding and resolving a class."""

        class Service:
            def get_message(self):
                return "Hello World"

        module = ModuleDef()
        module.make(Service).using().type(Service)

        injector = Injector()
        planner_input = PlannerInput([module])

        def get_service(service: Service) -> Service:
            return service

        service = injector.produce_run(planner_input, get_service)

        self.assertIsInstance(service, Service)
        self.assertEqual(service.get_message(), "Hello World")

    def test_instance_binding(self):
        """Test binding to a specific instance."""

        class Config:
            def __init__(self, name: str):
                self.name = name

        config_instance = Config("test-config")

        module = ModuleDef()
        module.make(Config).using().value(config_instance)

        injector = Injector()
        planner_input = PlannerInput([module])
        config = injector.produce(injector.plan(planner_input)).get(Config)

        self.assertIs(config, config_instance)
        self.assertEqual(config.name, "test-config")

    def test_factory_binding(self):
        """Test binding to a factory function."""

        def create_service() -> str:
            return "factory-created"

        module = ModuleDef()
        module.make(str).using().func(create_service)

        injector = Injector()
        planner_input = PlannerInput([module])
        result = injector.produce(injector.plan(planner_input)).get(str)

        self.assertEqual(result, "factory-created")


class TestDependencyInjection(unittest.TestCase):
    """Test dependency injection."""

    def test_constructor_injection(self):
        """Test dependency injection through constructor."""

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
        service = injector.produce(injector.plan(planner_input)).get(Service)

        self.assertIsInstance(service.database, Database)
        self.assertEqual(service.database.connection_string, "test-db")

    def test_optional_dependency(self):
        """Test handling of optional dependencies."""

        class OptionalService:
            def __init__(self, config: str | None = None):
                self.config = config or "default"

        module = ModuleDef()
        module.make(OptionalService).using().type(OptionalService)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(OptionalService)

        self.assertEqual(service.config, "default")


class TestTaggedBindings(unittest.TestCase):
    """Test tagged bindings."""

    def test_tagged_binding(self):
        """Test creating and resolving named bindings."""

        module = ModuleDef()
        module.make(str).named("prod").using().value("production-db")
        module.make(str).named("test").using().value("test-db")

        injector = Injector()
        planner_input = PlannerInput([module])

        locator = injector.produce(injector.plan(planner_input))
        prod_db = locator.get(str, "prod")
        test_db = locator.get(str, "test")

        self.assertEqual(prod_db, "production-db")
        self.assertEqual(test_db, "test-db")


class TestSetBindings(unittest.TestCase):
    """Test set bindings."""

    def test_set_binding(self):
        """Test collecting multiple implementations into a set."""

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
        service = injector.produce(injector.plan(planner_input)).get(Service)

        self.assertEqual(len(service.handlers), 2)
        self.assertIn(handler1, service.handlers)
        self.assertIn(handler2, service.handlers)


class TestSignatureIntrospection(unittest.TestCase):
    """Test signature introspection functionality."""

    def test_extract_class_dependencies(self):
        """Test extracting dependencies from a class constructor."""

        class Service:
            def __init__(self, database: str, config: int):
                pass

        deps = SignatureIntrospector.extract_from_class(Service)

        self.assertEqual(len(deps), 2)
        self.assertEqual(deps[0].name, "database")
        self.assertEqual(deps[0].type_hint, str)
        self.assertEqual(deps[1].name, "config")
        self.assertEqual(deps[1].type_hint, int)

    def test_extract_function_dependencies(self):
        """Test extracting dependencies from a function."""

        def factory(db: str, port: int) -> str:
            return f"{db}:{port}"

        deps = SignatureIntrospector.extract_from_callable(factory)

        self.assertEqual(len(deps), 2)
        self.assertEqual(deps[0].name, "db")
        self.assertEqual(deps[0].type_hint, str)
        self.assertEqual(deps[1].name, "port")
        self.assertEqual(deps[1].type_hint, int)

    def test_dataclass_dependencies(self):
        """Test extracting dependencies from a dataclass."""

        @dataclass
        class Config:
            host: str
            port: int
            debug: bool = False

        deps = SignatureIntrospector.extract_from_class(Config)

        self.assertEqual(len(deps), 3)
        # Check that optional field with default is detected
        debug_dep = next(d for d in deps if d.name == "debug")
        self.assertTrue(debug_dep.is_optional)


class TestGraphValidation(unittest.TestCase):
    """Test dependency graph validation."""

    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""

        class A:
            def __init__(self, b: "B"):
                self.b = b

        class B:
            def __init__(self, a: A):
                self.a = a

        module = ModuleDef()
        module.make(A).using().type(A)
        module.make(B).using().type(B)

        # Either circular dependency or missing dependency should be caught
        with self.assertRaises((CircularDependencyError, MissingBindingError)):
            injector = Injector()
            planner_input = PlannerInput([module])
            injector.produce(injector.plan(planner_input)).get(A)

    def test_missing_dependency_detection(self):
        """Test detection of missing dependencies."""

        class MissingDep:  # Define the missing dependency class for test
            pass

        class Service:
            def __init__(self, missing: MissingDep):
                self.missing = missing

        module = ModuleDef()
        module.make(Service).using().type(Service)

        with self.assertRaises(MissingBindingError):
            injector = Injector()
            planner_input = PlannerInput([module])
            injector.produce(injector.plan(planner_input)).get(Service)


class TestMultipleModules(unittest.TestCase):
    """Test combining multiple modules."""

    def test_module_composition(self):
        """Test combining multiple modules."""

        class Database:
            def __init__(self, host: str):
                self.host = host

        class Service:
            def __init__(self, database: Database):
                self.database = database

        # Base module
        base_module = ModuleDef()
        base_module.make(str).using().value("localhost")  # Default host
        base_module.make(Database).using().type(Database)

        # Extension module
        ext_module = ModuleDef()
        ext_module.make(Service).using().type(Service)

        injector = Injector()
        planner_input = PlannerInput([base_module, ext_module])
        service = injector.produce(injector.plan(planner_input)).get(Service)

        self.assertEqual(service.database.host, "localhost")


if __name__ == "__main__":
    unittest.main()
