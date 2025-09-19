#!/usr/bin/env python3
"""
Unit tests for the new algebraic implementation structure.
"""

import unittest

from izumi.distage import Injector, ModuleDef, PlannerInput
from izumi.distage.functoid import (
    class_functoid,
    function_functoid,
    set_element_functoid,
    value_functoid,
)
from izumi.distage.model import DIKey, InstanceKey, SetElementKey


class TestAlgebraicImplementations(unittest.TestCase):
    """Test algebraic implementation types."""

    def test_value_functoid(self):
        """Test value_functoid implementation."""
        value = "test-value"
        functoid = value_functoid(value)

        # For value functoids, call() returns the value directly
        self.assertEqual(functoid.keys(), [])
        self.assertEqual(functoid.call(), value)
        self.assertTrue("ValueFunctoid" in repr(functoid))

    def test_class_functoid(self):
        """Test class_functoid implementation."""

        class TestClass:
            pass

        functoid = class_functoid(TestClass)

        # For class functoids, call() creates an instance
        self.assertEqual(functoid.keys(), [])  # TestClass has no dependencies
        instance = functoid.call()
        self.assertIsInstance(instance, TestClass)
        self.assertTrue("ClassFunctoid" in repr(functoid))

    def test_function_functoid(self):
        """Test function_functoid implementation."""

        def test_func() -> str:
            return "test-result"

        functoid = function_functoid(test_func)

        # For function functoids, we can verify it by calling it
        self.assertEqual(functoid.keys(), [])  # test_func has no dependencies
        self.assertEqual(functoid.call(), "test-result")
        self.assertTrue("FunctionFunctoid" in repr(functoid))

    def test_set_element_functoid_with_value(self):
        """Test set_element_functoid wrapping value_functoid."""
        value = "element-value"
        inner_functoid = value_functoid(value)
        set_functoid = set_element_functoid(inner_functoid)

        # SetElementFunctoid delegates to inner functoid
        self.assertEqual(set_functoid.keys(), [])
        self.assertEqual(set_functoid.call(), value)
        self.assertTrue("SetElementFunctoid" in repr(set_functoid))

    def test_set_element_functoid_with_class(self):
        """Test set_element_functoid wrapping class_functoid."""

        class TestClass:
            pass

        inner_functoid = class_functoid(TestClass)
        set_functoid = set_element_functoid(inner_functoid)

        # SetElementFunctoid delegates to inner functoid
        self.assertEqual(set_functoid.keys(), [])
        instance = set_functoid.call()
        self.assertIsInstance(instance, TestClass)

    def test_set_element_functoid_with_func(self):
        """Test set_element_functoid wrapping function_functoid."""

        def test_func() -> str:
            return "func-result"

        inner_functoid = function_functoid(test_func)
        set_functoid = set_element_functoid(inner_functoid)

        # SetElementFunctoid delegates to inner functoid
        self.assertEqual(set_functoid.keys(), [])
        self.assertEqual(set_functoid.call(), "func-result")


class TestSetElementKey(unittest.TestCase):
    """Test SetElementKey functionality."""

    def test_set_element_key_creation(self):
        """Test creating SetElementKey."""
        set_key = InstanceKey(set[str], None)
        element_key = InstanceKey(str, "element-0")

        set_element_key = SetElementKey(set_key, element_key)

        self.assertEqual(set_element_key.set_key, set_key)
        self.assertEqual(set_element_key.element_key, element_key)

    def test_set_element_key_string_representation(self):
        """Test SetElementKey string representation."""
        set_key = InstanceKey(set[str], None)
        element_key = InstanceKey(str, "element-0")
        set_element_key = SetElementKey(set_key, element_key)

        # The actual string representation depends on how Python represents generic types
        result = str(set_element_key)
        self.assertIn("set", result)
        self.assertIn("element-0", result)
        self.assertIn("[", result)
        self.assertIn("]", result)

    def test_set_element_key_hashing(self):
        """Test SetElementKey hashing for dictionary keys."""
        set_key = InstanceKey(set[str], None)
        element_key1 = InstanceKey(str, "element-0")
        element_key2 = InstanceKey(str, "element-1")

        key1 = SetElementKey(set_key, element_key1)
        key2 = SetElementKey(set_key, element_key2)

        # Should be able to use as dictionary keys
        test_dict = {key1: "value1", key2: "value2"}

        self.assertEqual(test_dict[key1], "value1")
        self.assertEqual(test_dict[key2], "value2")
        self.assertEqual(len(test_dict), 2)


class TestFluentAPI(unittest.TestCase):
    """Test the new fluent API syntax."""

    def test_using_value_syntax(self):
        """Test .using().value() syntax."""
        module = ModuleDef()
        test_value = "test-string"

        module.make(str).using().value(test_value)

        injector = Injector()
        planner_input = PlannerInput([module])
        result = injector.produce(injector.plan(planner_input)).get(DIKey.of(str))

        self.assertEqual(result, test_value)

    def test_using_type_syntax(self):
        """Test .using().type() syntax."""

        class TestService:
            def get_message(self) -> str:
                return "Hello from TestService"

        module = ModuleDef()
        module.make(TestService).using().type(TestService)

        injector = Injector()
        planner_input = PlannerInput([module])
        result = injector.produce(injector.plan(planner_input)).get(DIKey.of(TestService))

        self.assertIsInstance(result, TestService)
        self.assertEqual(result.get_message(), "Hello from TestService")

    def test_using_func_syntax(self):
        """Test .using().func() syntax."""

        def create_string() -> str:
            return "factory-created-string"

        module = ModuleDef()
        module.make(str).using().func(create_string)

        injector = Injector()
        planner_input = PlannerInput([module])
        result = injector.produce(injector.plan(planner_input)).get(DIKey.of(str))

        self.assertEqual(result, "factory-created-string")

    def test_using_func_with_dependencies(self):
        """Test .using().func() with dependency injection."""

        class Config:
            def __init__(self, value: str):
                self.value = value

        def create_service(config: Config) -> str:
            return f"Service with {config.value}"

        module = ModuleDef()
        module.make(Config).using().value(Config("test-config"))
        module.make(str).using().func(create_service)

        injector = Injector()
        planner_input = PlannerInput([module])
        result = injector.produce(injector.plan(planner_input)).get(DIKey.of(str))

        self.assertEqual(result, "Service with test-config")

    def test_named_bindings_with_fluent_api(self):
        """Test named bindings with fluent API."""
        module = ModuleDef()
        module.make(str).named("primary").using().value("primary-value")
        module.make(str).named("secondary").using().value("secondary-value")

        injector = Injector()
        planner_input = PlannerInput([module])

        primary = injector.produce(injector.plan(planner_input)).get(DIKey.of(str, "primary"))
        secondary = injector.produce(injector.plan(planner_input)).get(DIKey.of(str, "secondary"))

        self.assertEqual(primary, "primary-value")
        self.assertEqual(secondary, "secondary-value")


class TestSetBindingsWithAlgebraicTypes(unittest.TestCase):
    """Test set bindings with the new algebraic implementation types."""

    def test_set_add_value(self):
        """Test set binding with .add_value()."""

        class ServiceWithSet:
            def __init__(self, items: set[str]):
                self.items = items

        module = ModuleDef()
        module.many(str).add_value("item1").add_value("item2")
        module.make(ServiceWithSet).using().type(ServiceWithSet)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithSet))

        self.assertEqual(service.items, {"item1", "item2"})

    def test_set_add_type(self):
        """Test set binding with .add_type()."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

            def __eq__(self, other):
                return isinstance(other, Handler) and self.name == other.name

            def __hash__(self):
                return hash(self.name)

        class Handler1(Handler):
            def __init__(self):
                super().__init__("handler1")

        class Handler2(Handler):
            def __init__(self):
                super().__init__("handler2")

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()
        module.many(Handler).add_type(Handler1).add_type(Handler2)
        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        handler_names = {handler.name for handler in service.handlers}
        self.assertEqual(handler_names, {"handler1", "handler2"})

    def test_set_add_func(self):
        """Test set binding with .add_func()."""

        def create_item1() -> str:
            return "factory-item1"

        def create_item2() -> str:
            return "factory-item2"

        class ServiceWithItems:
            def __init__(self, items: set[str]):
                self.items = items

        module = ModuleDef()
        module.many(str).add_func(create_item1).add_func(create_item2)
        module.make(ServiceWithItems).using().type(ServiceWithItems)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithItems))

        self.assertEqual(service.items, {"factory-item1", "factory-item2"})

    def test_set_mixed_implementation_types(self):
        """Test set binding with mixed implementation types."""

        def create_item() -> str:
            return "factory-item"

        class ItemCreator:
            def create(self) -> str:
                return "class-item"

        # We'll use a factory that creates ItemCreator and calls create()
        def item_from_creator(creator: ItemCreator) -> str:
            return creator.create()

        module = ModuleDef()
        module.make(ItemCreator).using().type(ItemCreator)

        class ServiceWithMixedItems:
            def __init__(self, items: set[str]):
                self.items = items

        module.many(str).add_value("direct-item").add_func(create_item).add_func(item_from_creator)
        module.make(ServiceWithMixedItems).using().type(ServiceWithMixedItems)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(
            DIKey.of(ServiceWithMixedItems)
        )

        self.assertEqual(service.items, {"direct-item", "factory-item", "class-item"})

    def test_backward_compatibility_set_add(self):
        """Test that .add() still works for backward compatibility."""

        class ServiceWithItems:
            def __init__(self, items: set[str]):
                self.items = items

        module = ModuleDef()
        module.many(str).add("item1").add("item2")
        module.make(ServiceWithItems).using().type(ServiceWithItems)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithItems))

        self.assertEqual(service.items, {"item1", "item2"})


class TestSetElementKeyIntegration(unittest.TestCase):
    """Test SetElementKey integration with dependency resolution."""

    def test_set_element_key_in_plan(self):
        """Test that SetElementKey is properly used in plan creation."""
        module = ModuleDef()
        module.many(str).add_value("test-item")

        injector = Injector()
        planner_input = PlannerInput([module])
        plan = injector.plan(planner_input)

        # Check that set bindings contain SetElementKey
        set_bindings = plan.graph.get_set_bindings(InstanceKey(set[str], None))
        self.assertEqual(len(set_bindings), 1)

        binding = set_bindings[0]
        self.assertIsInstance(binding.key, SetElementKey)
        self.assertEqual(binding.key.set_key.target_type, set[str])
        self.assertEqual(binding.key.element_key.target_type, str)
        self.assertTrue(binding.key.element_key.name.startswith("set-element-"))

    def test_set_element_dependency_resolution(self):
        """Test that set elements with dependencies resolve correctly."""

        class Config:
            def __init__(self, value: str):
                self.value = value

        class Service:
            def __init__(self, config: Config):
                self.config = config

            def get_name(self) -> str:
                return f"Service-{self.config.value}"

        def create_service_factory(config: Config) -> Service:
            return Service(config)

        module = ModuleDef()
        module.make(Config).using().value(Config("test"))
        module.many(Service).add_type(Service).add_func(create_service_factory)

        class AppWithServices:
            def __init__(self, services: set[Service]):
                self.services = services

        module.make(AppWithServices).using().type(AppWithServices)

        injector = Injector()
        planner_input = PlannerInput([module])
        app = injector.produce(injector.plan(planner_input)).get(DIKey.of(AppWithServices))

        self.assertEqual(len(app.services), 2)
        service_names = {service.get_name() for service in app.services}
        self.assertEqual(service_names, {"Service-test"})


class TestSetRefFunctionality(unittest.TestCase):
    """Test the .ref() functionality for sets."""

    def test_set_ref_basic(self):
        """Test that .ref() can add references to existing bindings to a set."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

            def handle(self) -> str:
                return f"handled by {self.name}"

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()

        # Create individual bindings
        module.make(Handler).named("primary").using().value(Handler("primary"))
        module.make(Handler).named("secondary").using().value(Handler("secondary"))

        # Use .ref() to add references to the set
        module.many(Handler).ref(DIKey.of(Handler, "primary")).ref(DIKey.of(Handler, "secondary"))

        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        self.assertEqual(len(service.handlers), 2)
        handler_names = {handler.name for handler in service.handlers}
        self.assertEqual(handler_names, {"primary", "secondary"})

    def test_set_ref_mixed_with_direct_elements(self):
        """Test that .ref() works together with .add_value() and other methods."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()

        # Create individual binding
        module.make(Handler).named("shared").using().value(Handler("shared"))

        # Mix .ref() with direct addition
        module.many(Handler).add_value(Handler("direct")).ref(DIKey.of(Handler, "shared"))

        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        self.assertEqual(len(service.handlers), 2)
        handler_names = {handler.name for handler in service.handlers}
        self.assertEqual(handler_names, {"direct", "shared"})


class TestWeakReferenceFunctionality(unittest.TestCase):
    """Test the .weak() functionality for sets."""

    def test_weak_reference_with_existing_binding(self):
        """Test that .weak() includes the binding when a non-weak reference exists."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()

        # Create a binding
        module.make(Handler).named("optional").using().value(Handler("optional"))

        # Add non-weak reference to the set
        module.many(Handler).ref(DIKey.of(Handler, "optional"))

        # Add weak reference to the same binding
        module.many(Handler).weak(DIKey.of(Handler, "optional"))

        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        # Should have the handler (included because of non-weak reference)
        self.assertEqual(len(service.handlers), 1)
        handler_names = {handler.name for handler in service.handlers}
        self.assertEqual(handler_names, {"optional"})

    def test_weak_reference_without_non_weak_counterpart(self):
        """Test that .weak() results in empty set when no non-weak reference exists."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()

        # Create a binding
        module.make(Handler).named("optional").using().value(Handler("optional"))

        # Add ONLY weak reference to the set (no non-weak reference)
        module.many(Handler).weak(DIKey.of(Handler, "optional"))

        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        # Should have empty set (weak reference filtered out)
        self.assertEqual(len(service.handlers), 0)

    def test_weak_reference_without_non_weak_counterpart_with_empty_set(self):
        """Test that .weak() results in empty set when combined with explicit empty set provision."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()

        # Create a binding
        module.make(Handler).named("optional").using().value(Handler("optional"))

        # Provide an empty set as default
        empty_set: set[Handler] = set()
        module.make(set[Handler]).using().value(empty_set)  # type: ignore[misc]

        # Add ONLY weak reference to the set (no non-weak reference)
        module.many(Handler).weak(DIKey.of(Handler, "optional"))

        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        # Should have empty set (weak reference filtered out, empty set used)
        self.assertEqual(len(service.handlers), 0)

    def test_weak_reference_mixed_with_direct_elements(self):
        """Test that .weak() works correctly when mixed with direct set elements."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()

        # Create bindings
        module.make(Handler).named("included").using().value(Handler("included"))
        module.make(Handler).named("excluded").using().value(Handler("excluded"))

        # Mix direct additions with weak references
        module.many(Handler).add_value(Handler("direct")).weak(DIKey.of(Handler, "included")).ref(
            DIKey.of(Handler, "included")
        ).weak(DIKey.of(Handler, "excluded"))

        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        # Should have direct + included (has non-weak ref), but not excluded (only weak ref)
        self.assertEqual(len(service.handlers), 2)
        handler_names = {handler.name for handler in service.handlers}
        self.assertEqual(handler_names, {"direct", "included"})

    def test_multiple_weak_references_same_binding(self):
        """Test multiple weak references to the same binding."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()

        # Create a binding
        module.make(Handler).named("shared").using().value(Handler("shared"))

        # Add multiple weak references (should be deduplicated and filtered out)
        module.many(Handler).weak(DIKey.of(Handler, "shared")).weak(DIKey.of(Handler, "shared"))

        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])

        # Should result in empty set because only weak references exist (no non-weak references)
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        # Should have empty set (only weak references, no non-weak)
        self.assertEqual(len(service.handlers), 0)

    def test_weak_reference_with_non_existent_binding(self):
        """Test that weak references to non-existent bindings are silently ignored."""

        class Handler:
            def __init__(self, name: str):
                self.name = name

        class ServiceWithHandlers:
            def __init__(self, handlers: set[Handler]):
                self.handlers = handlers

        module = ModuleDef()

        # Add weak reference to non-existent binding
        module.many(Handler).weak(DIKey.of(Handler, "nonexistent"))

        module.make(ServiceWithHandlers).using().type(ServiceWithHandlers)

        injector = Injector()
        planner_input = PlannerInput([module])
        service = injector.produce(injector.plan(planner_input)).get(DIKey.of(ServiceWithHandlers))

        # Weak reference to non-existent binding should be silently ignored
        self.assertEqual(len(service.handlers), 0)


if __name__ == "__main__":
    unittest.main()
