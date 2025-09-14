# PyDistage

A Python re-implementation of core concepts from Scala's [distage](https://izumi.7mind.io/distage/) dependency injection library.

## Features

PyDistage provides a powerful, type-safe dependency injection framework with:

- **DSL for defining bindings** - Fluent API for configuring dependencies
- **Signature introspection** - Automatic extraction of dependency requirements from type hints
- **Dependency graph formation and validation** - Build and validate the complete dependency graph at startup
- **Circular dependency detection** - Early detection of circular dependencies
- **Missing dependency detection** - Ensure all required dependencies are available
- **Tagged bindings** - Support for multiple implementations of the same interface
- **Set bindings** - Collect multiple implementations into sets
- **Factory functions** - Support for factory-based object creation

## Quick Start

```python
from distage_py import ModuleDef, Injector, Tag

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

# Configure bindings
module = ModuleDef()
module.make(str).from_("postgresql://localhost:5432/mydb")  # Connection string
module.make(Database).from_(Database)  # Database will get connection string injected
module.make(UserService).from_(UserService)  # UserService will get Database injected

# Create injector and resolve dependencies
injector = Injector(module)
user_service = injector.get(UserService)

# Use the service
result = user_service.create_user("alice")
print(result)  # DB[postgresql://localhost:5432/mydb]: INSERT INTO users (name) VALUES ('alice')
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

### Advanced Features

#### Tagged Bindings

Use tags to distinguish between different implementations:

```python
prod_tag = Tag("prod")
test_tag = Tag("test")

module = ModuleDef()
module.make(Database).tagged(prod_tag).from_(PostgresDB)
module.make(Database).tagged(test_tag).from_(InMemoryDB)

injector = Injector(module)
prod_db = injector.get(Database, prod_tag)
test_db = injector.get(Database, test_tag)
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

- **demo.py** - Comprehensive demonstration of all features
- **test_distage.py** - Unit tests covering all functionality

```bash
python demo.py          # Run the demo
python test_distage.py   # Run unit tests
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