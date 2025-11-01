# Chibi Izumi

[![CI](https://github.com/7mind/izumi-chibi-py/actions/workflows/ci.yml/badge.svg)](https://github.com/7mind/izumi-chibi-py/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/chibi-izumi.svg)](https://badge.fury.io/py/chibi-izumi)
[![codecov](https://codecov.io/gh/7mind/izumi-chibi-py/graph/badge.svg)](https://codecov.io/gh/7mind/izumi-chibi-py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python re-implementation of some core concepts from Scala's [Izumi Project](https://github.com/7mind/izumi),
`distage` staged dependency injection library in particular.

The port was done by guiding Claude with thorough manual reviews.

At this point the project is not battle-tested. Expect dragons, landmines and varying mileage.
Currently it powers just a couple of small private tools.

## Comparison with Other Python DI Libraries

| Library | GitHub Stars | Design | Staged DI | Config Axes | Async | Lifecycle | Factory | Type Safety | Maintainence |
|---------|--------------|--------|-----------|-------------|-------|-----------|---------|-------------|--------------|
| **chibi-izumi** | - | Non-invasive | ✅ Yes | ✅ Yes (Activations) | ✅ Full | ✅ Resource | ✅ Yes | ✅ Full | Active |
| [dependency-injector](https://github.com/ets-labs/python-dependency-injector) | ~4.6k | Decorator-based | ❌ Single-pass | ⚠️ Override-based | ✅ Coroutines | ✅ Resource | ✅ Yes | ✅ Good | Active (2025) |
| [dishka](https://github.com/reagento/dishka) | ~900 | Non-invasive | ⚠️ Unclear | ❌ Scopes only | ✅ Yes | ✅ Finalization | ✅ Yes | ✅ Good | Active |
| [injector](https://github.com/alecthomas/injector) | ~1.5k | Non-invasive | ❌ Single-pass | ❌ No | ⚠️ Unclear | ⚠️ Scopes | ✅ Yes | ✅ mypy | Active |
| [inject](https://github.com/ivankorobkov/python-inject) | ~740 | Decorator-based | ❌ Single-pass | ❌ No | ❌ No | ❌ No | ⚠️ Limited | ⚠️ Limited | Maintenance |
| [punq](https://github.com/bobthemighty/punq) | ~400 | IoC Container | ❌ Single-pass | ❌ No | ❌ No | ⚠️ Scopes | ✅ Yes | ✅ Good | Active |
| [lagom](https://github.com/meadsteve/lagom) | ~250 | Type-based | ❌ Single-pass | ❌ No | ✅ Yes | ⚠️ Scopes | ✅ Yes | ✅ Good | Active |
| [wireup](https://github.com/maldoinc/wireup) | ~220 | Non-invasive | ❌ Single-pass | ❌ No | ✅ Yes | ⚠️ Limited | ✅ Yes | ✅ Strong | Active |

**Legend:**
- ✅ Fully supported
- ⚠️ Partially supported or unclear
- ❌ Not supported or not documented

**Key Differentiators of chibi-izumi:**

1. **Staged Dependency Injection**: Multi-pass resolution allows validation before instantiation
2. **Configuration Axes (Activations)**: Explicitly choose between implementations based on environment/mode (prod/test/etc.)
3. **Comprehensive Async**: Full async/await support for factories, lifecycle, and execution
4. **Resource Management**: Automatic acquisition and cleanup with guaranteed LIFO release
5. **Non-invasive**: No decorators or base classes required in business logic
6. **Roles**: Multi-tenant application support with selective entrypoint execution

Most other libraries focus on single-pass injection and use scopes/overrides instead of explicit configuration axes.

## Features

Chibi Izumi provides a powerful, type-safe dependency injection framework with:

- **Non-invasive design** - Your classes remain framework-free, just use regular constructors
- **Type-safe bindings** - Algebraic data structure ensures binding correctness
- **Immutable bindings** - Bindings are defined once and cannot be modified
- **Explicit dependency graph** - All dependencies are explicit and traceable
- **Fail-fast validation** - Circular and missing dependencies are detected early
- **Zero-configuration features** - Automatic logger injection, factory patterns
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
- **Roles for multi-tenant applications** - Define multiple application entrypoints as roles that can be selectively executed
- **Lifecycle resource management** - Automatic acquisition and cleanup of resources with guaranteed release
- **Async support** - Full support for async factory functions, async lifecycle, and async dependency execution with automatic resource cleanup


## Limitations

This is a working implementation with some simplifications compared to the full distage library:

- No proxies and circular reference resolution
- No support for Testkit yet
- Forward references in type hints have limited support
- Simplified error messages compared to Scala version
- No dependency graph visualization tools
- **Proper Axis solver is not implemented yet**, instead currently we rely on simple filter-based approximation.


## Quick Start

```python
from izumi.distage import ModuleDef, Injector, PlannerInput
from izumi.distage.model import DIKey

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
user_service = injector.produce(injector.plan(planner_input)).get(DIKey.of(UserService))

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
from izumi.distage.model import DIKey

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
user_service = injector.produce(injector.plan(planner_input)).get(DIKey.of(UserService))
```

### Factory Bindings for Non-Singleton Semantics

Use `Factory[T]` when you need to create multiple instances with assisted injection:

```python
from typing import Annotated
from izumi.distage import Factory, Id, ModuleDef, Injector, PlannerInput
from izumi.distage.model import DIKey

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
factory = injector.produce(injector.plan(planner_input)).get(DIKey.of(Factory[UserSession]))

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
from izumi.distage.model import DIKey

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
db_service = injector.produce(injector.plan(planner_input)).get(DIKey.of(DatabaseService))
```

### Dependency Graph Validation

The dependency graph is built and validated when creating a plan:

```python
from izumi.distage import ModuleDef, Injector, PlannerInput
from izumi.distage.model import DIKey

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
from izumi.distage.model import DIKey

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
processor = injector.produce(injector.plan(planner_input)).get(DIKey.of(CommandProcessor))
# processor.handlers contains instances of both UserHandler and AdminHandler
```

### Activations for Configuration

Activations provide a powerful mechanism to choose between alternative implementations based on configuration axes:

```python
from izumi.distage import ModuleDef, Injector, PlannerInput
from izumi.distage.model import DIKey
from izumi.distage.activation import Activation, StandardAxis

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
prod_db = injector.produce(injector.plan(prod_input)).get(DIKey.of(Database))  # Gets PostgresDatabase

# Test setup
test_input = PlannerInput([module], activation=test_activation)
test_db = injector.produce(injector.plan(test_input)).get(DIKey.of(Database))  # Gets MockDatabase
```

## Advanced Usage Patterns

### Multiple Execution Patterns

```python
from izumi.distage import ModuleDef, Injector, PlannerInput
from izumi.distage.model import DIKey

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
service = locator.get(DIKey.of(UserService))

# Pattern 2: Function injection (recommended)
def business_logic(service: UserService, config: Config) -> str:
    return service.create_user(config.default_user)

result = injector.produce_run(planner_input, business_logic)

# Pattern 3: Simple get (for quick usage)
service = injector.produce(injector.plan(planner_input)).get(DIKey.of(UserService))
```

### Locator Inheritance

Locator inheritance allows you to create child injectors that inherit dependencies from parent locators. This enables you to create a base set of shared dependencies and then extend them with additional dependencies for specific use cases:

```python
from izumi.distage import ModuleDef, Injector, PlannerInput
from izumi.distage.model import DIKey

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
user_service = user_locator.get(DIKey.of(UserService))  # UserService + Database + DatabaseConfig
report_service = report_locator.get(DIKey.of(ReportService))  # ReportService + Database + DatabaseConfig

print(user_service.create_user("alice"))
print(report_service.generate_report())

```

Key benefits of locator inheritance:

- **Shared dependencies**: Define common dependencies once in the parent
- **Modular composition**: Each child can focus on specific functionality
- **Instance reuse**: Parent instances are shared across all children (singleton behavior preserved)
- **Override capability**: Child bindings take precedence over parent bindings
- **Multi-level inheritance**: Create inheritance chains for complex scenarios

### Roles - Multi-Tenant Applications

The Roles feature (inspired by [distage-framework Roles](https://izumi.7mind.io/distage/distage-framework.html#roles)) enables building flexible modular applications with multiple entrypoints. Define components as roles that can be selectively executed from a single codebase:

```python
import logging
from izumi.distage import ModuleDef, RoleAppMain, RoleTask, EntrypointArgs

# Define roles as classes with an 'id' attribute
class HelloTask(RoleTask):
    id = "hello"

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def start(self, args: EntrypointArgs) -> None:
        name = args.raw_args[0] if args.raw_args else "World"
        self.logger.info(f"Hello, {name}!")
        print(f"Hello, {name}!")

class GoodbyeTask(RoleTask):
    id = "goodbye"

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def start(self, args: EntrypointArgs) -> None:
        name = args.raw_args[0] if args.raw_args else "World"
        self.logger.info(f"Goodbye, {name}!")
        print(f"Goodbye, {name}!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Register roles
    module = ModuleDef()
    module.makeRole(HelloTask)
    module.makeRole(GoodbyeTask)

    # Create and run the application
    app = RoleAppMain()
    app.add_module(module)
    app.main()  # Parses sys.argv for role selection
```

**Usage:**
```bash
# Run single role
python app.py :hello Alice
# Output: Hello, Alice!

# Run multiple roles
python app.py :hello Alice :goodbye Bob
# Output:
# Hello, Alice!
# Goodbye, Bob!

# No roles specified
python app.py
# Output: No roles specified. Use :rolename to specify a role.
```

**Key features:**
- **Selective execution**: Only specified roles are instantiated and executed
- **Dependency injection**: Each role gets its own isolated DI context with resolved dependencies
- **CLI-based selection**: Use `:rolename arg1 arg2` syntax for role invocation
- **Multiple roles**: Execute multiple roles sequentially in a single run
- **Flexible architecture**: Build monoliths that can be split into microservices later

**Role types:**
- `RoleTask`: One-off tasks and batch jobs
- `RoleService`: Long-running services and daemons (both share the same base behavior currently)

This pattern enables building flexible monoliths where different entrypoints can be deployed independently or run together, without code duplication.

### Lifecycle - Resource Management

The Lifecycle feature (inspired by [distage Resource bindings](https://izumi.7mind.io/distage/basics.html#resource-bindings-lifecycle)) provides automatic resource management with guaranteed cleanup. Define acquire and release functions for resources like database connections:

```python
from izumi.distage import Injector, Lifecycle, ModuleDef, PlannerInput

class DBConnection:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connected = False

    def connect(self) -> None:
        print(f"Connecting to {self.connection_string}")
        self.connected = True

    def disconnect(self) -> None:
        print(f"Disconnecting from {self.connection_string}")
        self.connected = False

    def query(self, sql: str) -> str:
        assert self.connected, "Not connected"
        return f"Result: {sql}"

# Define lifecycle with acquire and release functions
def db_lifecycle(connection_string: str) -> Lifecycle[DBConnection]:
    def acquire() -> DBConnection:
        conn = DBConnection(connection_string)
        conn.connect()
        return conn

    def release(conn: DBConnection) -> None:
        conn.disconnect()

    return Lifecycle.make(acquire, release)

# Use lifecycle-managed resource
module = ModuleDef()
module.make(str).using().value("postgresql://localhost:5432/mydb")
module.make(DBConnection).using().fromResource(
    db_lifecycle("postgresql://localhost:5432/mydb")
)

def app(db: DBConnection) -> str:
    return db.query("SELECT * FROM users")

injector = Injector()
result = injector.produce_run(PlannerInput([module]), app)
# Resources are automatically acquired before app() and released after
```

**Key features:**
- **Automatic cleanup**: Resources are always released, even if exceptions occur
- **LIFO ordering**: Resources are released in reverse order of acquisition
- **Dependency injection**: Lifecycle acquire functions can have dependencies injected
- **Type-safe**: Full type checking for acquire and release functions

**Lifecycle constructors:**
- `Lifecycle.make(acquire, release)`: Standard lifecycle with explicit cleanup
- `Lifecycle.pure(value)`: Wrap a value without cleanup
- `Lifecycle.fromFactory(factory)`: Create from a factory function without cleanup

Resources are automatically managed within `locator.run()` or `injector.produce_run()` calls, ensuring proper cleanup even when errors occur.

### Async Support

Chibi Izumi provides comprehensive async support for modern Python applications. You can use async factory functions, async lifecycle management, and async dependency execution seamlessly:

```python
import asyncio
from izumi.distage import Injector, Lifecycle, ModuleDef, PlannerInput, InstanceKey

# Example: Async database connection
class AsyncDatabase:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connected = False

    async def connect(self) -> None:
        await asyncio.sleep(0.1)  # Simulate async connection
        print(f"Connected to {self.connection_string}")
        self.connected = True

    async def disconnect(self) -> None:
        await asyncio.sleep(0.1)  # Simulate async cleanup
        print(f"Disconnected from {self.connection_string}")
        self.connected = False

    async def query(self, sql: str) -> str:
        assert self.connected, "Not connected"
        await asyncio.sleep(0.05)  # Simulate async query
        return f"Result: {sql}"

# Async factory function
async def create_database(connection_string: str) -> AsyncDatabase:
    db = AsyncDatabase(connection_string)
    await db.connect()
    return db

# Async lifecycle with automatic cleanup
def db_lifecycle(connection_string: str) -> Lifecycle[AsyncDatabase]:
    async def acquire() -> AsyncDatabase:
        db = AsyncDatabase(connection_string)
        await db.connect()
        return db

    async def release(db: AsyncDatabase) -> None:
        await db.disconnect()

    return Lifecycle.make(acquire, release)

# Configure bindings
module = ModuleDef()
module.make(str).using().value("postgresql://localhost:5432/mydb")
module.make(AsyncDatabase).using().fromResource(
    db_lifecycle("postgresql://localhost:5432/mydb")
)

# Async application logic
async def app(db: AsyncDatabase) -> str:
    return await db.query("SELECT * FROM users")

# Use async context manager for automatic resource cleanup
async def main():
    injector = Injector()
    plan = injector.plan(PlannerInput([module]))

    # AsyncLocator provides automatic resource cleanup
    async with await injector.produce_async(plan) as locator:
        result = await locator.run(app)
        print(result)
    # Resources are automatically released here

asyncio.run(main())
```

**Key async features:**

- **Async factory functions**: Factory functions can be async and will be automatically awaited
- **Async lifecycle**: Both `acquire` and `release` can be async functions
- **AsyncLocator**: Async context manager ensures automatic resource cleanup
- **Mixed sync/async**: Seamlessly mix sync and async dependencies in the same graph
- **Automatic detection**: Framework automatically detects and handles async functions
- **LIFO cleanup**: Async resources are released in reverse order, even if errors occur

**Async Factory bindings:**

```python
import asyncio
from izumi.distage import Factory, Injector, Lifecycle, ModuleDef, PlannerInput, InstanceKey

# Reuse AsyncDatabase class from above
class AsyncDatabase:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connected = False

    async def connect(self) -> None:
        await asyncio.sleep(0.1)
        self.connected = True

# Async factory for on-demand instance creation
async def create_service(config: str) -> AsyncDatabase:
    db = AsyncDatabase(config)
    await db.connect()
    return db

module = ModuleDef()
module.make(Factory[AsyncDatabase]).using().factory_func(create_service)

async def use_factory():
    injector = Injector()
    plan = injector.plan(PlannerInput([module]))
    async with await injector.produce_async(plan) as locator:
        factory = locator.get(InstanceKey(Factory[AsyncDatabase]))
        # Create instances on-demand with async support
        db1 = await factory.create_async("config1")
        db2 = await factory.create_async("config2")
        assert db1.connected and db2.connected

asyncio.run(use_factory())
```

**Benefits of async support:**

- **Resource safety**: Automatic cleanup with async context managers
- **Performance**: True async/await support for I/O-bound operations
- **Flexibility**: Mix sync and async code without restrictions
- **Error handling**: Cleanup occurs even when exceptions are raised
- **Type safety**: Full type checking for async functions

## TODO: Future Features

The following concepts from the original Scala distage library are planned for future implementation:

### Framework - Advanced Features

The Framework module will provide additional features:

- **Health checks** - Built-in health monitoring for roles
- **Configuration integration** - Seamless integration with configuration management
- **Graceful shutdown** - Clean termination of long-running services
- **Plugin system** - Dynamic loading and management of plugins

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
