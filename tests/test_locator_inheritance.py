#!/usr/bin/env python3
"""
Unit tests for locator inheritance functionality.
"""

import unittest
from dataclasses import dataclass

from izumi.distage import Injector, ModuleDef, PlannerInput
from izumi.distage.model.graph import MissingBindingError


class TestLocatorInheritance(unittest.TestCase):
    """Test locator inheritance functionality."""

    def test_basic_inheritance(self):
        """Test basic parent-child locator inheritance."""

        @dataclass
        class Config:
            value: str

        @dataclass
        class DatabaseService:
            config: Config

            def get_data(self) -> str:
                return f"data-{self.config.value}"

        @dataclass
        class ApiService:
            db: DatabaseService

            def get_response(self) -> str:
                return f"api-{self.db.get_data()}"

        # Create parent module with Config and DatabaseService
        parent_module = ModuleDef()
        parent_module.make(Config).using().value(Config("production"))
        parent_module.make(DatabaseService).using().type(DatabaseService)

        parent_injector = Injector()
        parent_input = PlannerInput([parent_module])
        parent_plan = parent_injector.plan(parent_input)
        parent_locator = parent_injector.produce(parent_plan)

        # Create child module that only has ApiService
        child_module = ModuleDef()
        child_module.make(ApiService).using().type(ApiService)

        # Create child injector that inherits from parent
        child_injector = Injector.inherit(parent_locator)
        child_input = PlannerInput([child_module])
        child_plan = child_injector.plan(child_input)
        child_locator = child_injector.produce(child_plan)

        # Verify that child can access both its own and parent's dependencies
        api_service = child_locator.get(ApiService)
        self.assertIsInstance(api_service, ApiService)
        self.assertEqual(api_service.get_response(), "api-data-production")

        # Verify that child can access parent dependencies directly
        config = child_locator.get(Config)
        self.assertIsInstance(config, Config)
        self.assertEqual(config.value, "production")

        db_service = child_locator.get(DatabaseService)
        self.assertIsInstance(db_service, DatabaseService)
        self.assertEqual(db_service.get_data(), "data-production")

    def test_child_overrides_parent(self):
        """Test that child bindings override parent bindings."""

        @dataclass
        class Service:
            name: str

        # Parent module with one implementation
        parent_module = ModuleDef()
        parent_module.make(Service).using().value(Service("parent"))

        parent_injector = Injector()
        parent_input = PlannerInput([parent_module])
        parent_plan = parent_injector.plan(parent_input)
        parent_locator = parent_injector.produce(parent_plan)

        # Child module with different implementation
        child_module = ModuleDef()
        child_module.make(Service).using().value(Service("child"))

        child_injector = Injector.inherit(parent_locator)
        child_input = PlannerInput([child_module])
        child_plan = child_injector.plan(child_input)
        child_locator = child_injector.produce(child_plan)

        # Child should use its own binding, not parent's
        service = child_locator.get(Service)
        self.assertEqual(service.name, "child")

        # Parent should still have its own binding
        parent_service = parent_locator.get(Service)
        self.assertEqual(parent_service.name, "parent")

    def test_named_bindings_inheritance(self):
        """Test inheritance with named bindings."""

        @dataclass
        class Database:
            name: str

        @dataclass
        class Service:
            primary_db: Database
            cache_db: Database

        # Parent module with named bindings
        parent_module = ModuleDef()
        parent_module.make(Database).named("primary").using().value(Database("primary"))
        parent_module.make(Database).named("cache").using().value(Database("cache"))

        parent_injector = Injector()
        parent_input = PlannerInput([parent_module])
        parent_plan = parent_injector.plan(parent_input)
        parent_locator = parent_injector.produce(parent_plan)

        # Child module that depends on parent's named bindings
        child_module = ModuleDef()

        def create_service(primary_db: Database, cache_db: Database) -> Service:
            return Service(primary_db, cache_db)

        child_module.make(Service).using().func(create_service)

        child_injector = Injector.inherit(parent_locator)
        child_input = PlannerInput([child_module])

        # This should fail because the child doesn't know about the named dependencies
        # during planning phase (automatic dependency resolution during signature introspection)
        with self.assertRaises(MissingBindingError):
            child_injector.plan(child_input)

    def test_manual_named_dependency_resolution(self):
        """Test manual resolution of named dependencies from parent."""

        @dataclass
        class Database:
            name: str

        # Parent module with named bindings
        parent_module = ModuleDef()
        parent_module.make(Database).named("primary").using().value(Database("primary"))
        parent_module.make(Database).named("cache").using().value(Database("cache"))

        parent_injector = Injector()
        parent_input = PlannerInput([parent_module])
        parent_plan = parent_injector.plan(parent_input)
        parent_locator = parent_injector.produce(parent_plan)

        # Child can manually access named dependencies from parent
        child_injector = Injector.inherit(parent_locator)
        child_input = PlannerInput([ModuleDef()])  # Empty module
        child_plan = child_injector.plan(child_input)
        child_locator = child_injector.produce(child_plan)

        # Access named dependencies directly
        primary_db = child_locator.get(Database, "primary")
        cache_db = child_locator.get(Database, "cache")

        self.assertEqual(primary_db.name, "primary")
        self.assertEqual(cache_db.name, "cache")

    def test_multi_level_inheritance(self):
        """Test inheritance across multiple levels."""

        @dataclass
        class Level1Service:
            name: str = "level1"

        @dataclass
        class Level2Service:
            level1: Level1Service
            name: str = "level2"

        @dataclass
        class Level3Service:
            level1: Level1Service
            level2: Level2Service
            name: str = "level3"

        # Level 1 injector
        level1_module = ModuleDef()
        level1_module.make(Level1Service).using().type(Level1Service)

        level1_injector = Injector()
        level1_input = PlannerInput([level1_module])
        level1_plan = level1_injector.plan(level1_input)
        level1_locator = level1_injector.produce(level1_plan)

        # Level 2 injector inherits from level 1
        level2_module = ModuleDef()
        level2_module.make(Level2Service).using().type(Level2Service)

        level2_injector = Injector.inherit(level1_locator)
        level2_input = PlannerInput([level2_module])
        level2_plan = level2_injector.plan(level2_input)
        level2_locator = level2_injector.produce(level2_plan)

        # Level 3 injector inherits from level 2
        level3_module = ModuleDef()
        level3_module.make(Level3Service).using().type(Level3Service)

        level3_injector = Injector.inherit(level2_locator)
        level3_input = PlannerInput([level3_module])
        level3_plan = level3_injector.plan(level3_input)
        level3_locator = level3_injector.produce(level3_plan)

        # Level 3 should be able to access all services
        level3_service = level3_locator.get(Level3Service)
        self.assertIsInstance(level3_service, Level3Service)
        self.assertEqual(level3_service.name, "level3")
        self.assertEqual(level3_service.level1.name, "level1")
        self.assertEqual(level3_service.level2.name, "level2")

    def test_locator_parent_properties(self):
        """Test locator parent access properties."""

        @dataclass
        class Service:
            name: str

        # Create parent locator
        parent_module = ModuleDef()
        parent_module.make(Service).using().value(Service("parent"))

        parent_injector = Injector()
        parent_input = PlannerInput([parent_module])
        parent_plan = parent_injector.plan(parent_input)
        parent_locator = parent_injector.produce(parent_plan)

        # Create child locator
        child_module = ModuleDef()
        child_injector = Injector.inherit(parent_locator)
        child_input = PlannerInput([child_module])
        child_plan = child_injector.plan(child_input)
        child_locator = child_injector.produce(child_plan)

        # Test parent properties
        self.assertFalse(parent_locator.has_parent())
        self.assertIsNone(parent_locator.parent)

        self.assertTrue(child_locator.has_parent())
        self.assertIs(child_locator.parent, parent_locator)

    def test_instance_caching_across_inheritance(self):
        """Test that instances are properly cached when inherited."""

        class SingletonService:
            _instance_count = 0

            def __init__(self):
                SingletonService._instance_count += 1
                self.instance_id = SingletonService._instance_count

        @dataclass
        class ClientService:
            singleton: SingletonService

        # Reset counter
        SingletonService._instance_count = 0

        # Create parent with singleton
        parent_module = ModuleDef()
        parent_module.make(SingletonService).using().type(SingletonService)

        parent_injector = Injector()
        parent_input = PlannerInput([parent_module])
        parent_plan = parent_injector.plan(parent_input)
        parent_locator = parent_injector.produce(parent_plan)

        # Get singleton from parent
        parent_singleton = parent_locator.get(SingletonService)
        self.assertEqual(parent_singleton.instance_id, 1)

        # Create child
        child_module = ModuleDef()
        child_module.make(ClientService).using().type(ClientService)

        child_injector = Injector.inherit(parent_locator)
        child_input = PlannerInput([child_module])
        child_plan = child_injector.plan(child_input)
        child_locator = child_injector.produce(child_plan)

        # Get client service which depends on singleton
        client_service = child_locator.get(ClientService)
        self.assertEqual(client_service.singleton.instance_id, 1)

        # Get singleton directly from child
        child_singleton = child_locator.get(SingletonService)
        self.assertEqual(child_singleton.instance_id, 1)

        # All should be the same instance
        self.assertIs(parent_singleton, client_service.singleton)
        self.assertIs(parent_singleton, child_singleton)

        # Should only have created one instance
        self.assertEqual(SingletonService._instance_count, 1)

    def test_error_when_dependency_missing_in_both(self):
        """Test that proper error is raised when dependency is missing in both parent and child."""

        @dataclass
        class MissingService:
            name: str

        @dataclass
        class ClientService:
            missing: MissingService

        # Create parent without MissingService
        parent_module = ModuleDef()
        parent_injector = Injector()
        parent_input = PlannerInput([parent_module])
        parent_plan = parent_injector.plan(parent_input)
        parent_locator = parent_injector.produce(parent_plan)

        # Create child without MissingService
        child_module = ModuleDef()
        child_module.make(ClientService).using().type(ClientService)

        child_injector = Injector.inherit(parent_locator)
        child_input = PlannerInput([child_module])

        # Should fail during planning because MissingService is not bound anywhere
        with self.assertRaises(MissingBindingError) as cm:
            child_injector.plan(child_input)

        self.assertIn("MissingService", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
