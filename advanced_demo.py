#!/usr/bin/env python3
"""
Advanced PyDistage Demo - showcasing Roots and Activations.

This demo demonstrates the corrected distage implementation with:
1. Roots for dependency tracing and garbage collection
2. Activations for choosing between alternative bindings
3. Multiple axes of configuration (Mode, Repo, World)
4. Proper dependency graph pruning based on roots
"""

from abc import ABC, abstractmethod

from distage_py import Activation, Injector, ModuleDef, Roots, StandardAxis
from distage_py.activation import Axis, AxisChoiceDef


# Define custom axis for our demo
class Style(Axis):
    """Custom axis for different UI styles."""

    class Normal(AxisChoiceDef):
        def __init__(self):
            super().__init__("Normal")

    class AllCaps(AxisChoiceDef):
        def __init__(self):
            super().__init__("AllCaps")

    Normal = Normal()
    AllCaps = AllCaps()


# Domain interfaces
class Database(ABC):
    @abstractmethod
    def query(self, sql: str) -> str:
        pass


class MessageService(ABC):
    @abstractmethod
    def send_message(self, message: str) -> str:
        pass


class Logger(ABC):
    @abstractmethod
    def log(self, message: str) -> None:
        pass


# Production implementations
class PostgresDatabase(Database):
    def __init__(self, connection_string: str = "postgresql://prod:5432/app"):
        self.connection_string = connection_string

    def query(self, sql: str) -> str:
        return f"PostgresDB[{self.connection_string}]: {sql}"


class EmailService(MessageService):
    def __init__(self, database: Database):
        self.database = database

    def send_message(self, message: str) -> str:
        self.database.query("INSERT INTO email_log ...")
        return f"Email sent: {message}"


class FileLogger(Logger):
    def __init__(self):
        pass

    def log(self, message: str) -> None:
        print(f"[FILE_LOG] {message}")


# Test implementations
class InMemoryDatabase(Database):
    def query(self, sql: str) -> str:
        return f"InMemoryDB: {sql}"


class MockMessageService(MessageService):
    def send_message(self, message: str) -> str:
        return f"Mock message: {message}"


class ConsoleLogger(Logger):
    def log(self, message: str) -> None:
        print(f"[CONSOLE] {message}")


# Different greeters for style axis
class NormalGreeter:
    def __init__(self, message_service: MessageService, logger: Logger):
        self.message_service = message_service
        self.logger = logger

    def greet(self, name: str) -> str:
        self.logger.log(f"Greeting {name}")
        return self.message_service.send_message(f"Hello, {name}!")


class AllCapsGreeter:
    def __init__(self, message_service: MessageService, logger: Logger):
        self.message_service = message_service
        self.logger = logger

    def greet(self, name: str) -> str:
        self.logger.log(f"GREETING {name.upper()}")
        return self.message_service.send_message(f"HELLO, {name.upper()}!")


# Dummy implementations
class DummyDatabase(Database):
    def query(self, sql: str) -> str:  # noqa: ARG002
        return "dummy_result"


# Unused service (for garbage collection demo)
class UnusedService:
    def __init__(self):
        print("UnusedService created (this shouldn't happen with proper roots!)")

    def do_something(self) -> str:
        return "unused"


# Application entry point
class Application:
    def __init__(
        self, greeter: NormalGreeter
    ):  # Note: specifically requires NormalGreeter for demo
        self.greeter = greeter

    def run(self) -> str:
        return self.greeter.greet("World")


def main():
    """Demonstrate advanced distage features."""
    print("=== Advanced PyDistage Demo: Roots and Activations ===\n")

    # Create modules with multiple implementations
    base_module = ModuleDef()

    # Database bindings with different modes
    base_module.make(Database).tagged(StandardAxis.Mode.Prod).from_(PostgresDatabase)
    base_module.make(Database).tagged(StandardAxis.Mode.Test).from_(InMemoryDatabase)
    base_module.make(Database).tagged(StandardAxis.Repo.Dummy).from_(DummyDatabase)

    # Message service bindings
    base_module.make(MessageService).tagged(StandardAxis.World.Real).from_(EmailService)
    base_module.make(MessageService).tagged(StandardAxis.World.Mock).from_(MockMessageService)

    # Logger bindings
    base_module.make(Logger).tagged(StandardAxis.Mode.Prod).from_(FileLogger)
    base_module.make(Logger).tagged(StandardAxis.Mode.Test).from_(ConsoleLogger)

    # Greeter bindings with custom axis
    base_module.make(NormalGreeter).tagged(Style.Normal).from_(NormalGreeter)
    base_module.make(AllCapsGreeter).tagged(Style.AllCaps).from_(AllCapsGreeter)

    # Application binding
    base_module.make(Application).from_(Application)

    # Unused service (should be garbage collected when using roots)
    base_module.make(UnusedService).from_(UnusedService)

    print("1. Production Configuration:")
    print("-" * 40)

    prod_activation = Activation(
        {
            StandardAxis.Mode: StandardAxis.Mode.Prod,
            StandardAxis.World: StandardAxis.World.Real,
            Style: Style.Normal,
        }
    )

    # Use specific roots to only instantiate what we need
    app_roots = Roots.target(Application)

    try:
        injector = Injector(base_module, roots=app_roots, activation=prod_activation)
        app = injector.get(Application)
        result = app.run()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n2. Test Configuration:")
    print("-" * 40)

    test_activation = Activation(
        {
            StandardAxis.Mode: StandardAxis.Mode.Test,
            StandardAxis.World: StandardAxis.World.Mock,
            Style: Style.Normal,
        }
    )

    try:
        injector = Injector(base_module, roots=app_roots, activation=test_activation)
        app = injector.get(Application)
        result = app.run()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n3. All-Caps Style Configuration:")
    print("-" * 40)

    # This should fail because Application requires NormalGreeter but we're using AllCaps
    caps_activation = Activation(
        {
            StandardAxis.Mode: StandardAxis.Mode.Test,
            StandardAxis.World: StandardAxis.World.Mock,
            Style: Style.AllCaps,
        }
    )

    try:
        injector = Injector(base_module, roots=app_roots, activation=caps_activation)
        app = injector.get(Application)
        result = app.run()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Expected error (AllCapsGreeter doesn't match NormalGreeter requirement): {e}")

    print("\n4. Dummy Repository Configuration:")
    print("-" * 40)

    dummy_activation = Activation(
        {
            StandardAxis.Repo: StandardAxis.Repo.Dummy,
            StandardAxis.Mode: StandardAxis.Mode.Test,  # Need to specify Mode for Logger
            StandardAxis.World: StandardAxis.World.Mock,
            Style: Style.Normal,
        }
    )

    try:
        injector = Injector(base_module, roots=app_roots, activation=dummy_activation)
        app = injector.get(Application)
        result = app.run()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n5. Everything vs Roots Comparison:")
    print("-" * 40)

    print("With specific roots (should not create UnusedService):")
    try:
        injector_with_roots = Injector(base_module, roots=app_roots, activation=test_activation)
        app = injector_with_roots.get(Application)
        print("✓ Application created without UnusedService")
    except Exception as e:
        print(f"Error: {e}")

    print("\nWith everything roots (will create all bindings):")
    try:
        injector_everything = Injector(
            base_module, roots=Roots.everything(), activation=test_activation
        )
        injector_everything.get(UnusedService)
        print("✓ UnusedService was created (demonstrates no garbage collection)")
    except Exception as e:
        print(f"Error: {e}")

    print("\n6. Multiple Roots:")
    print("-" * 40)

    # Create roots for both Application and UnusedService
    multi_roots = Roots.target(Application, UnusedService)

    try:
        injector = Injector(base_module, roots=multi_roots, activation=test_activation)
        app = injector.get(Application)
        injector.get(UnusedService)
        print("✓ Both Application and UnusedService created as specified by roots")
    except Exception as e:
        print(f"Error: {e}")

    print("\nDemo completed successfully!")


if __name__ == "__main__":
    main()
