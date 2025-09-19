#!/usr/bin/env python3
"""
Demo of named dependency injection using Id annotations.

This demo shows how to use Annotated types with Id annotations to create
named dependencies, allowing multiple bindings of the same type to coexist.
"""

from dataclasses import dataclass
from typing import Annotated

from izumi.distage import Id, Injector, ModuleDef, PlannerInput
from izumi.distage.model import DIKey


# Domain classes
@dataclass
class DatabaseConfig:
    """Configuration for database connections."""

    host: str
    port: int
    database: str
    username: str
    password: str

    def to_url(self) -> str:
        return (
            f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        )


class DatabaseConnection:
    """A database connection."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.url = config.to_url()

    def query(self, sql: str) -> str:
        return f"[DB:{self.config.database}] Executing: {sql}"


class UserService:
    """Service for managing users."""

    def __init__(
        self,
        primary_db: Annotated[DatabaseConnection, Id("primary-db")],
        replica_db: Annotated[DatabaseConnection, Id("replica-db")],
        cache_ttl: Annotated[int, Id("cache-ttl")],
    ):
        self.primary_db = primary_db
        self.replica_db = replica_db
        self.cache_ttl = cache_ttl

    def create_user(self, username: str) -> str:
        result = self.primary_db.query(f"INSERT INTO users (username) VALUES ('{username}')")
        return f"{result} [Cache TTL: {self.cache_ttl}s]"

    def get_user(self, user_id: int) -> str:
        result = self.replica_db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return f"{result} [Cache TTL: {self.cache_ttl}s]"


class ReportService:
    """Service for generating reports."""

    def __init__(
        self,
        analytics_db: Annotated[DatabaseConnection, Id("analytics-db")],
        batch_size: Annotated[int, Id("batch-size")],
    ):
        self.analytics_db = analytics_db
        self.batch_size = batch_size

    def generate_report(self, report_type: str) -> str:
        result = self.analytics_db.query(
            f"SELECT * FROM {report_type}_data LIMIT {self.batch_size}"
        )
        return f"Report generated: {result}"


class Application:
    """Main application."""

    def __init__(
        self,
        user_service: UserService,
        report_service: ReportService,
        app_name: Annotated[str, Id("app-name")],
        version: Annotated[str, Id("app-version")],
    ):
        self.user_service = user_service
        self.report_service = report_service
        self.app_name = app_name
        self.version = version

    def run(self) -> str:
        print(f"Starting {self.app_name} v{self.version}")

        # Create a user
        user_result = self.user_service.create_user("alice")
        print(f"User creation: {user_result}")

        # Get a user
        get_result = self.user_service.get_user(123)
        print(f"User retrieval: {get_result}")

        # Generate a report
        report_result = self.report_service.generate_report("sales")
        print(f"Report: {report_result}")

        return "Application completed successfully"


def create_database_config(
    host: Annotated[str, Id("host")],
    port: Annotated[int, Id("port")],
    database: Annotated[str, Id("database")],
    username: Annotated[str, Id("username")],
    password: Annotated[str, Id("password")],
) -> DatabaseConfig:
    """Factory function that creates DatabaseConfig from named dependencies."""
    return DatabaseConfig(host, port, database, username, password)


def main():
    """Demonstrate named dependency injection."""
    print("=== Named Dependencies Demo ===\n")

    # Create module with named bindings
    module = ModuleDef()

    # Application metadata
    module.make(str).named("app-name").using().value("MultiDB Application")
    module.make(str).named("app-version").using().value("2.0.0")

    # Cache configuration
    module.make(int).named("cache-ttl").using().value(300)  # 5 minutes
    module.make(int).named("batch-size").using().value(1000)

    # Primary database configuration (using explicit values)
    module.make(DatabaseConfig).named("primary-config").using().value(
        DatabaseConfig(
            host="primary-db.example.com",
            port=5432,
            database="users",
            username="app_user",
            password="secret123",
        )
    )

    # Replica database configuration (using factory function with named deps)
    module.make(str).named("host").using().value("replica-db.example.com")
    module.make(int).named("port").using().value(5432)
    module.make(str).named("database").using().value("users_replica")
    module.make(str).named("username").using().value("readonly_user")
    module.make(str).named("password").using().value("readonly_pass")
    module.make(DatabaseConfig).named("replica-config").using().func(create_database_config)

    # Analytics database configuration (direct instance)
    analytics_config = DatabaseConfig(
        host="analytics.example.com",
        port=5432,
        database="analytics",
        username="analytics_user",
        password="analytics_pass",
    )
    module.make(DatabaseConfig).named("analytics-config").using().value(analytics_config)

    # Database connections (each gets a different config)
    def create_primary_connection(
        config: Annotated[DatabaseConfig, Id("primary-config")],
    ) -> DatabaseConnection:
        return DatabaseConnection(config)

    def create_replica_connection(
        config: Annotated[DatabaseConfig, Id("replica-config")],
    ) -> DatabaseConnection:
        return DatabaseConnection(config)

    def create_analytics_connection(
        config: Annotated[DatabaseConfig, Id("analytics-config")],
    ) -> DatabaseConnection:
        return DatabaseConnection(config)

    module.make(DatabaseConnection).named("primary-db").using().func(create_primary_connection)
    module.make(DatabaseConnection).named("replica-db").using().func(create_replica_connection)
    module.make(DatabaseConnection).named("analytics-db").using().func(create_analytics_connection)

    # Services
    module.make(UserService).using().type(UserService)
    module.make(ReportService).using().type(ReportService)
    module.make(Application).using().type(Application)

    print("1. Creating application with named dependencies...")
    print("-" * 50)

    # Create and run application
    injector = Injector()
    planner_input = PlannerInput([module])

    try:
        app = injector.produce(injector.plan(planner_input)).get(DIKey.of(Application))
        result = app.run()
        print(f"\n{result}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n2. Demonstrating individual named dependency resolution...")
    print("-" * 50)

    # Show individual named dependencies
    app_name = injector.produce(injector.plan(planner_input)).get(DIKey.of(str, "app-name"))
    version = injector.produce(injector.plan(planner_input)).get(DIKey.of(str, "app-version"))
    cache_ttl = injector.produce(injector.plan(planner_input)).get(DIKey.of(int, "cache-ttl"))

    print(f"App Name: {app_name}")
    print(f"Version: {version}")
    print(f"Cache TTL: {cache_ttl}")

    # Show different database connections
    primary_db = injector.produce(injector.plan(planner_input)).get(
        DIKey.of(DatabaseConnection, "primary-db")
    )
    replica_db = injector.produce(injector.plan(planner_input)).get(
        DIKey.of(DatabaseConnection, "replica-db")
    )
    analytics_db = injector.produce(injector.plan(planner_input)).get(
        DIKey.of(DatabaseConnection, "analytics-db")
    )

    print(f"\nPrimary DB: {primary_db.url}")
    print(f"Replica DB: {replica_db.url}")
    print(f"Analytics DB: {analytics_db.url}")

    print("\n3. Demonstrating function injection with named dependencies...")
    print("-" * 50)

    def business_logic(
        primary: Annotated[DatabaseConnection, Id("primary-db")],
        analytics: Annotated[DatabaseConnection, Id("analytics-db")],
        app_name: Annotated[str, Id("app-name")],
    ) -> str:
        primary_query = primary.query("SELECT COUNT(*) FROM users")
        analytics_query = analytics.query("SELECT SUM(revenue) FROM sales")
        return f"[{app_name}] {primary_query} | {analytics_query}"

    business_result = injector.produce_run(planner_input, business_logic)
    print(f"Business logic result: {business_result}")

    print("\n4. Error handling - missing named dependency...")
    print("-" * 50)

    # Try to get a non-existent named dependency
    try:
        missing = injector.produce(injector.plan(planner_input)).get(
            DIKey.of(str, "non-existent-name")
        )
        print(f"Unexpected success: {missing}")
    except Exception as e:
        print(f"Expected error for missing dependency: {e}")

    print("\nDemo completed successfully!")


if __name__ == "__main__":
    main()
