#!/usr/bin/env python3
"""
Demonstration of Chibi Izumi - Python implementation of distage concepts.

This demo shows:
1. Basic dependency injection with classes
2. Factory functions
3. Instance bindings
4. Tagged bindings
5. Set bindings for collecting multiple implementations
6. Dependency graph validation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from izumi.distage import Injector, ModuleDef, PlannerInput

# Example domain: A simple web service with different components


class Database(ABC):
    """Abstract database interface."""

    @abstractmethod
    def query(self, sql: str) -> str:
        pass


class PostgresDB(Database):
    """PostgreSQL implementation."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def query(self, sql: str) -> str:
        return f"PostgreSQL[{self.connection_string}]: {sql}"


class InMemoryDB(Database):
    """In-memory database for testing."""

    def query(self, sql: str) -> str:
        return f"InMemoryDB: {sql}"


@dataclass
class Config:
    """Application configuration."""

    app_name: str
    debug: bool = False


class Logger:
    """Simple logger."""

    def __init__(self, config: Config):
        self.config = config

    def log(self, message: str) -> None:
        prefix = f"[{self.config.app_name}]"
        if self.config.debug:
            prefix += "[DEBUG]"
        print(f"{prefix} {message}")


class UserService:
    """Service for managing users."""

    def __init__(self, database: Database, logger: Logger):
        self.database = database
        self.logger = logger

    def create_user(self, username: str) -> str:
        self.logger.log(f"Creating user: {username}")
        result = self.database.query(f"INSERT INTO users (name) VALUES ('{username}')")
        return result


# Command pattern implementation for set bindings
class Command(ABC):
    """Base command interface."""

    @abstractmethod
    def execute(self) -> str:
        pass


class StartCommand(Command):
    """Command to start the application."""

    def __init__(self, logger: Logger):
        self.logger = logger

    def execute(self) -> str:
        self.logger.log("Starting application...")
        return "Application started"


class StatusCommand(Command):
    """Command to check application status."""

    def __init__(self, logger: Logger):
        self.logger = logger

    def execute(self) -> str:
        self.logger.log("Checking status...")
        return "Application is running"


class CommandExecutor:
    """Executes all available commands."""

    def __init__(self, commands: set[Command]):
        self.commands = commands

    def execute_all(self) -> list[str]:
        return [cmd.execute() for cmd in self.commands]


# Factory function example
def create_connection_string(config: Config) -> str:
    """Factory function to create database connection string."""
    if config.debug:
        return "postgresql://localhost:5432/testdb"
    else:
        return "postgresql://prod-server:5432/proddb"


def main():
    """Main demo function."""
    print("=== Chibi Izumi Demo ===\n")

    # Define names for different environments

    # Production module
    prod_module = ModuleDef()
    prod_module.make(Config).using().value(Config("ProductionApp", debug=False))
    prod_module.make(str).using().func(create_connection_string)  # Connection string factory
    prod_module.make(Database).using().type(
        PostgresDB
    )  # Class binding - will resolve constructor deps
    prod_module.make(Logger).using().type(Logger)  # Class binding
    prod_module.make(UserService).using().type(UserService)

    # Set bindings for commands
    prod_module.many(Command).add_type(StartCommand)
    prod_module.many(Command).add_type(StatusCommand)
    prod_module.make(CommandExecutor).using().type(CommandExecutor)

    # Test module (adds additional bindings)
    test_module = ModuleDef()
    test_module.make(Database).named("test").using().value(InMemoryDB())  # Instance binding

    print("1. Production Environment:")
    print("-" * 30)

    try:
        injector = Injector()
        planner_input = PlannerInput([prod_module])

        # Get various services
        user_service = injector.produce(injector.plan(planner_input)).get(UserService)
        result = user_service.create_user("alice")
        print(f"Result: {result}")

        # Get command executor and run commands
        executor = injector.produce(injector.plan(planner_input)).get(CommandExecutor)
        command_results = executor.execute_all()
        for cmd_result in command_results:
            print(f"Command result: {cmd_result}")

    except Exception as e:
        print(f"Error in production setup: {e}")

    print("\n2. Test Environment:")
    print("-" * 30)

    try:
        # Combine modules - test module overrides will take precedence
        injector = Injector()
        planner_input = PlannerInput([prod_module, test_module])

        config = injector.produce(injector.plan(planner_input)).get(Config)
        print(f"Config: {config}")

        # This will use the test database
        database = injector.produce(injector.plan(planner_input)).get(Database, "test")
        result = database.query("SELECT * FROM users")
        print(f"Test DB result: {result}")

    except Exception as e:
        print(f"Error in test setup: {e}")

    print("\n3. Dependency Graph Validation:")
    print("-" * 30)

    # Example of circular dependency detection
    circular_module = ModuleDef()

    class A:
        def __init__(self, b: "B"):
            self.b = b

    class B:
        def __init__(self, a: A):
            self.a = a

    circular_module.make(A).using().type(A)
    circular_module.make(B).using().type(B)

    try:
        injector = Injector()
        planner_input = PlannerInput([circular_module])
        injector.plan(planner_input)  # This triggers validation
        print(
            "This shouldn't print - circular dependency should be caught during graph construction"
        )
    except Exception as e:
        print(f"Caught expected circular dependency: {e}")

    print("\n4. Missing Dependency Detection:")
    print("-" * 30)

    class MissingService:  # Define the missing service class for demo
        pass

    class ServiceWithMissingDep:
        def __init__(self, missing_service: MissingService):
            self.missing_service = missing_service

    incomplete_module = ModuleDef()
    incomplete_module.make(ServiceWithMissingDep).using().type(ServiceWithMissingDep)

    try:
        injector = Injector()
        planner_input = PlannerInput([incomplete_module])
        injector.plan(planner_input)  # This triggers validation
        print(
            "This shouldn't print - missing dependency should be caught during graph construction"
        )
    except Exception as e:
        print(f"Caught expected missing dependency: {e}")

    print("\nDemo completed successfully!")


if __name__ == "__main__":
    main()
