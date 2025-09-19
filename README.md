# Chibi Izumi

[![CI](https://github.com/7mind/izumi-chibi-py/actions/workflows/ci.yml/badge.svg)](https://github.com/7mind/izumi-chibi-py/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/chibi-izumi.svg)](https://badge.fury.io/py/chibi-izumi)
[![codecov](https://codecov.io/gh/7mind/izumi-chibi-py/graph/badge.svg)](https://codecov.io/gh/7mind/izumi-chibi-py)

A Python re-implementation of some core concepts from Scala's [Izumi Project](https://github.com/7mind/izumi),
`distage` staged dependency injection library in particular.

The port was done by guiding Claude with thorough manual reviews.

At this point the project is not battle-tested. Expect dragons, landmines and varying mileage.

## Other generic DI implementations for Python

1. [dishka](https://github.com/reagento/dishka) - staged dependency injection, no explicit support for configurability (axes)
2. [dependency_injector](https://pypi.org/project/dependency-injector/) - single-pass, no explicit support for configurability (axes)
3. [inject](https://pypi.org/project/inject/) - invasive, based on decorators, single-pass, no explicit support for configurability (axes)

## Features

`distage` provides a powerful, type-safe dependency injection framework with:

- **Non-invasive design** - No decorators, base classes, or framework-specific code required in your business logic
- **Fluent DSL for defining bindings** - Type-safe API with `.using().value()/.type()/.func()/.factory_type()/.factory_func()`
- **Signature introspection** - Automatic extraction of dependency requirements from type hints
- **Dependency graph formation and validation** - Build and validate the complete dependency graph at startup
- **Automatic logger injection** - Seamless injection of location-based loggers without manual setup
- **Factory bindings** - Create new instances on-demand with assisted injection (`Factory[T]`)
- **Named dependencies** - Distinguished dependencies using `@Id` annotations
- **Roots for dependency tracing** - Specify what components should be instantiated
- **Activations for configuration** - Choose between alternative implementations using configuration axes
- **Garbage collection** - Only instantiate components reachable from roots
- **Circular dependency detection** - Early detection of circular dependencies
- **Missing dependency detection** - Ensure all required dependencies are available
- **Tagged bindings** - Support for multiple implementations of the same interface
- **Set bindings** - Collect multiple implementations into sets
- **Locator inheritance** - Create child injectors that inherit dependencies from parent locators

## Quick Start

```python
from izumi.distage import ModuleDef, Injector, PlannerInput

# Define your classes
class Database:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def query(self, sql: str) -> str:
        return f"DB[{self.connection_string}]: {sql}"

class UserService:
    def __init__(self, database: Database):
        self.database = database

    def create_user(self, name: str) -> str:
        return self.database.query(f"INSERT INTO users (name) VALUES ('{name}')")

# Configure bindings using the new fluent API
module = ModuleDef()
module.make(str).using().value("postgresql://prod:5432/app")
module.make(Database).using().type(Database)  # Constructor injection
module.make(UserService).using().type(UserService)

# Create injector and get service
injector = Injector()
planner_input = PlannerInput([module])
user_service = injector.produce(injector.plan(planner_input)).get(UserService)

# Use the service
result = user_service.create_user("alice")
print(result)  # DB[postgresql://prod:5432/app]: INSERT INTO users (name) VALUES ('alice')
```

## Core Concepts

### ModuleDef - Binding Definition DSL

The `ModuleDef` class provides a fluent DSL for defining dependency bindings:

```python
from izumi.distage import ModuleDef, Factory

# Example classes for demonstration
class Config:
    def __init__(self, debug: bool = False, db_url: str = ""):
        self.debug = debug
        self.db_url = db_url

class Database:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

class PostgresDatabase(Database):
    def __init__(self, connection_string: str):
        super().__init__(connection_string)

class UserService:
    def __init__(self, database: Database):
        self.database = database

class Handler:
    def handle(self):
        pass

class UserHandler(Handler):
    def handle(self):
        return "user"

class AdminHandler(Handler):
    def handle(self):
        return "admin"

# Now define the bindings
module = ModuleDef()

# Instance binding
module.make(Config).using().value(Config(debug=True))

# Class binding (constructor injection)
module.make(Database).using().type(PostgresDatabase)

# Factory function binding
def create_database(config: Config) -> Database:
    return Database(config.db_url)

module.make(Database).named("custom").using().func(create_database)

# Factory bindings for non-singleton semantics
module.make(Factory[UserService]).using().factory_type(UserService)

# Named bindings for multiple instances
module.make(str).named("db-url").using().value("postgresql://prod:5432/app")
module.make(str).named("api-key").using().value("secret-key-123")

# Set bindings for collecting multiple implementations
module.many(Handler).add_type(UserHandler)
module.many(Handler).add_type(AdminHandler)
```

### Automatic Logger Injection

Chibi Izumi automatically provides loggers for dependencies without names, creating location-specific logger instances:

```python
import logging
from izumi.distage import ModuleDef, Injector, PlannerInput

class Database:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def query(self, sql: str) -> str:
        return f"DB[{self.connection_string}]: {sql}"

class UserService:
    # Logger automatically injected based on class location
    def __init__(self, database: Database, logger: logging.Logger):
        self.database = database
        self.logger = logger  # Will be logging.getLogger("__main__.UserService")

    def create_user(self, name: str) -> str:
        self.logger.info(f"Creating user: {name}")
        return self.database.query(f"INSERT INTO users (name) VALUES ('{name}')")

# No need to configure loggers - they're injected automatically!
module = ModuleDef()
module.make(str).using().value("postgresql://prod:5432/app")
module.make(Database).using().type(Database)
module.make(UserService).using().type(UserService)

injector = Injector()
planner_input = PlannerInput([module])
user_service = injector.produce(injector.plan(planner_input)).get(UserService)
```

### Factory Bindings for Non-Singleton Semantics

Use `Factory[T]` when you need to create multiple instances with assisted injection:

```python
from typing import Annotated
from izumi.distage import Factory, Id, ModuleDef, Injector, PlannerInput

class Database:
    def __init__(self, connection_string: Annotated[str, Id("db-url")]):
        self.connection_string = connection_string

class UserSession:
    def __init__(self, database: Database, user_id: str, api_key: Annotated[str, Id("api-key")]):
        self.database = database
        self.user_id = user_id
        self.api_key = api_key

module = ModuleDef()
module.make(str).named("db-url").using().value("postgresql://prod:5432/app")
module.make(Database).using().type(Database)
module.make(Factory[UserSession]).using().factory_type(UserSession)

injector = Injector()
planner_input = PlannerInput([module])
factory = injector.produce(injector.plan(planner_input)).get(Factory[UserSession])

# Create new instances with runtime parameters
session1 = factory.create("user123", **{"api-key": "secret1"})
session2 = factory.create("user456", **{"api-key": "secret2"})
# Database is injected from DI, user_id and api_key are provided at creation time
```

### Named Dependencies with @Id

Use `@Id` annotations to distinguish between multiple bindings of the same type:

```python
from typing import Annotated
from izumi.distage import Id, ModuleDef, Injector, PlannerInput

class DatabaseService:
    def __init__(
        self,
        primary_db: Annotated[str, Id("primary-db")],
        replica_db: Annotated[str, Id("replica-db")]
    ):
        self.primary_db = primary_db
        self.replica_db = replica_db

module = ModuleDef()
module.make(str).named("primary-db").using().value("postgresql://primary:5432/app")
module.make(str).named("replica-db").using().value("postgresql://replica:5432/app")
module.make(DatabaseService).using().type(DatabaseService)

injector = Injector()
planner_input = PlannerInput([module])
db_service = injector.produce(injector.plan(planner_input)).get(DatabaseService)
```

### Dependency Graph Validation

The dependency graph is built and validated when creating a plan:

```python
from izumi.distage import ModuleDef, Injector, PlannerInput

class A:
    def __init__(self, b: "B"):
        self.b = b

class B:
    def __init__(self, a: A):
        self.a = a

# This will detect circular dependencies
module = ModuleDef()
module.make(A).using().type(A)
module.make(B).using().type(B)

try:
    injector = Injector()
    planner_input = PlannerInput([module])
    plan = injector.plan(planner_input)  # Validation happens here
    print("This should not print - circular dependency should be caught")
except Exception as e:
    # Catches circular dependencies, missing dependencies, etc.
    pass  # Expected to happen
```

### Set Bindings

Collect multiple implementations into a set:

```python
from izumi.distage import ModuleDef, Injector, PlannerInput

class CommandHandler:
    def handle(self, cmd: str) -> str:
        pass

class UserHandler(CommandHandler):
    def handle(self, cmd: str) -> str:
        return f"User: {cmd}"

class AdminHandler(CommandHandler):
    def handle(self, cmd: str) -> str:
        return f"Admin: {cmd}"

class CommandProcessor:
    def __init__(self, handlers: set[CommandHandler]):
        self.handlers = handlers

module = ModuleDef()
module.many(CommandHandler).add_type(UserHandler)
module.many(CommandHandler).add_type(AdminHandler)
module.make(CommandProcessor).using().type(CommandProcessor)

injector = Injector()
planner_input = PlannerInput([module])
processor = injector.produce(injector.plan(planner_input)).get(CommandProcessor)
# processor.handlers contains instances of both UserHandler and AdminHandler
```

### Activations for Configuration

Activations provide a powerful mechanism to choose between alternative implementations based on configuration axes:

```python
from izumi.distage import ModuleDef, Injector, PlannerInput, Activation, StandardAxis

# Define different implementations for different environments
class Database:
    def query(self, sql: str) -> str:
        pass

class PostgresDatabase(Database):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def query(self, sql: str) -> str:
        return f"Postgres[{self.connection_string}]: {sql}"

class MockDatabase(Database):
    def query(self, sql: str) -> str:
        return f"Mock: {sql}"

# Configure bindings with activations
module = ModuleDef()

# Database implementations based on environment
module.make(str).using().value("postgresql://prod:5432/app")
module.make(Database).tagged(StandardAxis.Mode.Prod).using().type(PostgresDatabase)
module.make(Database).tagged(StandardAxis.Mode.Test).using().type(MockDatabase)

# Create activations to select implementations
prod_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Prod})
test_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Test})

injector = Injector()

# Production setup
prod_input = PlannerInput([module], activation=prod_activation)
prod_db = injector.produce(injector.plan(prod_input)).get(Database)  # Gets PostgresDatabase

# Test setup
test_input = PlannerInput([module], activation=test_activation)
test_db = injector.produce(injector.plan(test_input)).get(Database)  # Gets MockDatabase
```

## Advanced Usage Patterns

### Multiple Execution Patterns

```python
from izumi.distage import ModuleDef, Injector, PlannerInput

class Config:
    def __init__(self, default_user: str = "test"):
        self.default_user = default_user

class UserService:
    def __init__(self, config: Config):
        self.config = config

    def create_user(self, name: str) -> str:
        return f"Created user: {name}"

module = ModuleDef()
module.make(Config).using().type(Config)
module.make(UserService).using().type(UserService)

injector = Injector()
planner_input = PlannerInput([module])

# Pattern 1: Plan + Locator (most control)
plan = injector.plan(planner_input)
locator = injector.produce(plan)
service = locator.get(UserService)

# Pattern 2: Function injection (recommended)
def business_logic(service: UserService, config: Config) -> str:
    return service.create_user(config.default_user)

result = injector.produce_run(planner_input, business_logic)

# Pattern 3: Simple get (for quick usage)
service = injector.produce(injector.plan(planner_input)).get(UserService)
```

### Locator Inheritance

Locator inheritance allows you to create child injectors that inherit dependencies from parent locators. This enables you to create a base set of shared dependencies and then extend them with additional dependencies for specific use cases:

```python
from izumi.distage import ModuleDef, Injector, PlannerInput

# Shared services
class DatabaseConfig:
    def __init__(self, connection_string: str = "postgresql://prod:5432/app"):
        self.connection_string = connection_string

class Database:
    def __init__(self, config: DatabaseConfig):
        self.config = config

    def query(self, sql: str) -> str:
        return f"DB[{self.config.connection_string}]: {sql}"

# Application-specific services
class UserService:
    def __init__(self, database: Database):
        self.database = database

    def create_user(self, name: str) -> str:
        return self.database.query(f"INSERT INTO users (name) VALUES ('{name}')")

class ReportService:
    def __init__(self, database: Database):
        self.database = database

    def generate_report(self) -> str:
        return self.database.query("SELECT COUNT(*) FROM users")

# 1. Create parent injector with shared dependencies
parent_module = ModuleDef()
parent_module.make(DatabaseConfig).using().type(DatabaseConfig)
parent_module.make(Database).using().type(Database)

parent_injector = Injector()
parent_input = PlannerInput([parent_module])
parent_plan = parent_injector.plan(parent_input)
parent_locator = parent_injector.produce(parent_plan)

# 2. Create child injector for user operations
user_module = ModuleDef()
user_module.make(UserService).using().type(UserService)

user_injector = Injector.inherit(parent_locator)
user_input = PlannerInput([user_module])
user_plan = user_injector.plan(user_input)
user_locator = user_injector.produce(user_plan)

# 3. Create another child injector for reporting
report_module = ModuleDef()
report_module.make(ReportService).using().type(ReportService)

report_injector = Injector.inherit(parent_locator)
report_input = PlannerInput([report_module])
report_plan = report_injector.plan(report_input)
report_locator = report_injector.produce(report_plan)

# 4. Use the services - child locators inherit parent dependencies
user_service = user_locator.get(UserService)  # UserService + Database + DatabaseConfig
report_service = report_locator.get(ReportService)  # ReportService + Database + DatabaseConfig

print(user_service.create_user("alice"))
print(report_service.generate_report())

```

Key benefits of locator inheritance:

- **Shared dependencies**: Define common dependencies once in the parent
- **Modular composition**: Each child can focus on specific functionality
- **Instance reuse**: Parent instances are shared across all children (singleton behavior preserved)
- **Override capability**: Child bindings take precedence over parent bindings
- **Multi-level inheritance**: Create inheritance chains for complex scenarios

## Architecture

Chibi Izumi follows these design principles from the original distage:

1. **Non-invasive design** - Your classes remain framework-free, just use regular constructors
2. **Type-safe bindings** - Algebraic data structure ensures binding correctness
3. **Immutable bindings** - Bindings are defined once and cannot be modified
4. **Explicit dependency graph** - All dependencies are explicit and traceable
5. **Fail-fast validation** - Circular and missing dependencies are detected early
6. **Zero-configuration features** - Automatic logger injection, factory patterns

## Limitations

This is a working implementation with some simplifications compared to the full distage library:

- Forward references in type hints have limited support
- No advanced lifecycle management (startup/shutdown hooks)
- Simplified error messages compared to Scala version
- No compile-time dependency graph visualization tools

## TODO: Future Features

The following concepts from the original Scala distage library are planned for future implementation:

### Framework - Roles and Flexible Monoliths

The Framework module will provide:

- **Role-based application structure** - Define application components as roles that can be started/stopped independently
- **Flexible monoliths** - Run multiple roles in a single process or distribute them across processes
- **Lifecycle management** - Automatic startup/shutdown hooks for resources
- **Health checks** - Built-in health monitoring for roles
- **Configuration integration** - Seamless integration with configuration management
- **Resource management** - Proper cleanup of resources like database connections, file handles

### Testkit - Testing Support

The Testkit module will provide:

- **Test fixtures integration** - Automatic setup/teardown of test dependencies
- **Test-specific activations** - Easy switching between test and production implementations
- **Mock injection** - Seamless replacement of dependencies with mocks
- **Test isolation** - Each test gets its own isolated dependency graph
- **Docker test containers** - Integration with testcontainers for integration tests
- **Parallel test execution** - Safe concurrent test execution with isolated contexts

## Contributing

This project was developed through AI-assisted programming with thorough manual review. Contributions, bug reports, and feedback are welcome!
