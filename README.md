# PyDistage

A Python re-implementation of core concepts from Scala's [distage](https://izumi.7mind.io/distage/) dependency injection library.

## Features

PyDistage provides a powerful, type-safe dependency injection framework with:

- **DSL for defining bindings** - Fluent API for configuring dependencies
- **Signature introspection** - Automatic extraction of dependency requirements from type hints
- **Dependency graph formation and validation** - Build and validate the complete dependency graph at startup
- **Roots for dependency tracing** - Specify what components should be instantiated
- **Activations for configuration** - Choose between alternative implementations using configuration axes
- **Garbage collection** - Only instantiate components reachable from roots
- **Circular dependency detection** - Early detection of circular dependencies
- **Missing dependency detection** - Ensure all required dependencies are available
- **Tagged bindings** - Support for multiple implementations of the same interface
- **Set bindings** - Collect multiple implementations into sets
- **Factory functions** - Support for factory-based object creation

## Quick Start

```python
from distage_py import ModuleDef, Injector, Roots, Activation, StandardAxis

# Define your classes
class Database:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def query(self, sql: str) -> str:
        return f"DB[{self.connection_string}]: {sql}"

class ProdDatabase(Database):
    def __init__(self):
        super().__init__("postgresql://prod:5432/app")

class TestDatabase(Database):
    def __init__(self):
        super().__init__("sqlite://memory")

class UserService:
    def __init__(self, database: Database):
        self.database = database
    
    def create_user(self, name: str) -> str:
        return self.database.query(f"INSERT INTO users (name) VALUES ('{name}')")

# Configure bindings with activations
module = ModuleDef()
module.make(Database).tagged(StandardAxis.Mode.Prod).from_(ProdDatabase)
module.make(Database).tagged(StandardAxis.Mode.Test).from_(TestDatabase)
module.make(UserService).from_(UserService)

# Create injector with roots and activation
roots = Roots.target(UserService)  # Only instantiate UserService and its dependencies
activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Prod})

injector = Injector(module, roots=roots, activation=activation)
user_service = injector.get(UserService)

# Use the service
result = user_service.create_user("alice")
print(result)  # DB[postgresql://prod:5432/app]: INSERT INTO users (name) VALUES ('alice')
```

## Core Concepts

### ModuleDef - Binding Definition DSL

The `ModuleDef` class provides a fluent DSL for defining dependency bindings:

```python
module = ModuleDef()

# Class binding
module.make(Service).from_(ServiceImpl)

# Instance binding  
module.make(Config).from_(Config(debug=True))

# Factory function binding
module.make(Database).from_(lambda config: create_database(config.db_url))

# Tagged bindings for multiple implementations
prod_tag = Tag("prod")
test_tag = Tag("test")
module.make(Database).tagged(prod_tag).from_(PostgresDatabase)
module.make(Database).tagged(test_tag).from_(InMemoryDatabase)

# Set bindings for collecting multiple implementations
module.many(Handler).add(UserHandler).add(AdminHandler)
```

### Signature Introspection

PyDistage automatically analyzes constructor signatures and type hints to determine dependencies:

```python
class UserService:
    def __init__(self, database: Database, logger: Logger, config: Optional[Config] = None):
        # database and logger will be injected
        # config is optional and will use default if no binding exists
        pass
```

The introspection system handles:
- Required dependencies (no default value)
- Optional dependencies (with default values)
- Type hints and forward references
- Dataclass field analysis

### Dependency Graph Validation

The dependency graph is built and validated when the `Injector` is created:

```python
try:
    injector = Injector(module)
except CircularDependencyError as e:
    print(f"Circular dependency detected: {e}")
except MissingBindingError as e:
    print(f"Missing dependency: {e}")
```

### Roots - Dependency Tracing

Roots define which components should be instantiated from your dependency graph, enabling garbage collection of unused bindings:

```python
from distage_py import Roots, DIKey

# Target specific types as roots
roots = Roots.target(UserService, Logger)

# Include everything (no garbage collection)  
roots = Roots.everything()

# Create custom roots
roots = Roots([DIKey.get(UserService), DIKey.get(Logger, tag)])
```

### Activations - Configuration Axes

Activations allow choosing between different implementations using configuration axes:

```python
from distage_py import Activation, StandardAxis

# Built-in axes
activation = Activation({
    StandardAxis.Mode: StandardAxis.Mode.Prod,    # Prod vs Test
    StandardAxis.World: StandardAxis.World.Real,  # Real vs Mock
    StandardAxis.Repo: StandardAxis.Repo.Prod     # Prod vs Dummy
})

# Custom axes
class Priority(Axis):
    class High(AxisChoiceDef):
        def __init__(self): super().__init__("High")
    class Low(AxisChoiceDef):
        def __init__(self): super().__init__("Low")
    
    High, Low = High(), Low()

module.make(Service).tagged(Priority.High).from_(HighPriorityService)
module.make(Service).tagged(Priority.Low).from_(LowPriorityService)

activation = Activation({Priority: Priority.High})
```

### Advanced Features

#### Tagged Bindings

Use activation tags to distinguish between different implementations:

```python
from distage_py import StandardAxis

module = ModuleDef()
module.make(Database).tagged(StandardAxis.Mode.Prod).from_(PostgresDB)
module.make(Database).tagged(StandardAxis.Mode.Test).from_(InMemoryDB)

# Activation selects which binding to use
prod_activation = Activation({StandardAxis.Mode: StandardAxis.Mode.Prod})
injector = Injector(module, activation=prod_activation)
db = injector.get(Database)  # Will get PostgresDB
```

#### Set Bindings

Collect multiple implementations into a set:

```python
from typing import Set

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
    def __init__(self, handlers: Set[CommandHandler]):
        self.handlers = handlers

module = ModuleDef()
module.many(CommandHandler).add(UserHandler).add(AdminHandler)
module.make(CommandProcessor).from_(CommandProcessor)

injector = Injector(module)
processor = injector.get(CommandProcessor)
# processor.handlers contains instances of both UserHandler and AdminHandler
```

## Project Structure

```
distage_py/
├── __init__.py          # Main exports
├── core.py              # ModuleDef, Injector, Tag classes
├── bindings.py          # Binding definitions and types
├── introspection.py     # Signature analysis utilities
├── graph.py             # Dependency graph management
└── resolver.py          # Dependency resolution engine
```

## Running Examples

- **demo.py** - Basic demonstration of core features
- **advanced_demo.py** - Advanced demonstration of roots and activations
- **test_distage.py** - Unit tests covering basic functionality  
- **test_advanced_distage.py** - Unit tests for roots and activations

```bash
python demo.py                    # Run basic demo
python advanced_demo.py          # Run advanced demo with roots/activations  
python test_distage.py           # Run basic tests
python test_advanced_distage.py  # Run advanced tests
```

## Architecture

PyDistage follows these design principles from the original distage:

1. **Compile-time safety** - Dependencies are validated at injector creation time
2. **No runtime reflection** - Uses type hints and signature inspection
3. **Immutable bindings** - Bindings are defined once and cannot be modified
4. **Explicit dependency graph** - All dependencies are explicit and traceable
5. **Fail-fast validation** - Circular and missing dependencies are detected early

## Limitations

This is a demo implementation with some simplifications compared to the full distage library:

- Forward reference resolution is simplified
- No support for higher-kinded types
- Limited lifecycle management
- No built-in support for effect types (IO, ZIO, etc.)
- Simplified error handling

## Inspired By

This project is inspired by [7mind's distage library](https://izumi.7mind.io/distage/) for Scala, which provides advanced dependency injection capabilities for functional programming patterns.
