# Claude Code Instructions

## Code Style Guidelines
- Always use explicit imports without "if TYPE_CHECKING" pattern
- Use actual types instead of quoted class names in type annotations
- Follow the existing code style and patterns in the project

## Development Commands

### Quick Commands
- Run all checks: `uv run python scripts.py check`
- Run tests only: `uv run python scripts.py test`
- Run linting only: `uv run python scripts.py lint`
- Run type checking only: `uv run python scripts.py typecheck`

### Individual Commands
- Run tests: `uv run pytest`
- Run linting: `uv run ruff check`
- Run type checking: `uv run mypy .` or `uv run pyright .`
- Auto-fix formatting: `uv run ruff format .`
- Auto-fix linting: `uv run ruff check --fix`

## Runtime Type Checking
The project uses [beartype](https://github.com/beartype/beartype) for runtime type checking:
- Beartype is integrated through `distage_py/__init__.py`
- Applied selectively to core classes (`Injector`, `ModuleDef`) to avoid issues with complex generics
- Configured to throw errors for type violations (strict mode)
- Decorator application warnings about generic types are expected and harmless
- Type violations in user code will raise `BeartypeCallHintViolation` exceptions

## Project Structure
This is a Python dependency injection library (`distage-py`) that implements concepts from Scala's distage library.