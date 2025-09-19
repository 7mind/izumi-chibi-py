#!/usr/bin/env python3
"""
Demo of automatic logger injection in the distage-py dependency injection system.

This demo shows how loggers are automatically injected based on the location
where they are requested, eliminating the need for manual logger setup.
"""

import logging
from typing import Annotated

from izumi.distage import Id, Injector, ModuleDef, PlannerInput

# Configure logging to see the output
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")


# Example services that need loggers
class DatabaseService:
    """A database service that automatically gets a logger."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def connect(self) -> str:
        self.logger.info("Connecting to database...")
        return "Connected to database"

    def query(self, sql: str) -> str:
        self.logger.info(f"Executing query: {sql}")
        return f"Result for: {sql}"


class UserService:
    """A user service with dependencies and automatic logger injection."""

    def __init__(self, database: DatabaseService, logger: logging.Logger):
        self.database = database
        self.logger = logger

    def create_user(self, username: str) -> str:
        self.logger.info(f"Creating user: {username}")
        result = self.database.query(f"INSERT INTO users (name) VALUES ('{username}')")
        self.logger.info(f"User created successfully: {username}")
        return result


class EmailService:
    """An email service with automatic logger injection."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def send_email(self, to: str, subject: str) -> str:
        self.logger.info(f"Sending email to {to}: {subject}")
        return f"Email sent to {to}"


class NotificationService:
    """A service that uses multiple dependencies with automatic loggers."""

    def __init__(self, email_service: EmailService, logger: logging.Logger):
        self.email_service = email_service
        self.logger = logger

    def notify_user_created(self, username: str, email: str) -> str:
        self.logger.info(f"Notifying about new user: {username}")
        return self.email_service.send_email(email, f"Welcome {username}!")


class ManualLoggerService:
    """A service that uses a manually configured logger."""

    def __init__(self, logger: Annotated[logging.Logger, Id("manual-logger")]):
        self.logger = logger

    def do_something(self) -> str:
        self.logger.info("Doing something with manual logger")
        return "Manual logger used"


def create_audit_message(logger: logging.Logger, user_service: UserService) -> str:  # noqa: ARG001
    """A factory function that also gets automatic logger injection."""
    logger.info("Creating audit message...")
    return "Audit: User service operations logged"


def main():
    """Demonstrate automatic logger injection."""
    print("=== Automatic Logger Injection Demo ===\n")

    # Create module with service bindings - no logger bindings needed!
    module = ModuleDef()
    module.make(DatabaseService).using().type(DatabaseService)
    module.make(UserService).using().type(UserService)
    module.make(EmailService).using().type(EmailService)
    module.make(NotificationService).using().type(NotificationService)

    # For the factory function
    module.make(str).named("audit").using().func(create_audit_message)

    # Only for the manual logger service, we need an explicit binding
    manual_logger = logging.getLogger("my.custom.logger")
    module.make(logging.Logger).named("manual-logger").using().value(manual_logger)
    module.make(ManualLoggerService).using().type(ManualLoggerService)

    injector = Injector()
    planner_input = PlannerInput([module])

    print("1. Basic automatic logger injection:")
    print("-" * 40)

    # Get the database service - it should have a logger named after its location
    db_service = injector.produce(injector.plan(planner_input)).get(DatabaseService)
    print(f"DatabaseService logger name: {db_service.logger.name}")
    result = db_service.connect()
    print(f"Result: {result}")

    print("\n2. Nested dependencies with automatic loggers:")
    print("-" * 40)

    # Get the user service - both it and its DatabaseService dependency should have loggers
    user_service = injector.produce(injector.plan(planner_input)).get(UserService)
    print(f"UserService logger name: {user_service.logger.name}")
    print(f"UserService.database logger name: {user_service.database.logger.name}")
    result = user_service.create_user("alice")
    print(f"Result: {result}")

    print("\n3. Multiple services with different logger names:")
    print("-" * 40)

    # Get different services - they should have different logger names
    email_service = injector.produce(injector.plan(planner_input)).get(EmailService)
    notification_service = injector.produce(injector.plan(planner_input)).get(NotificationService)

    print(f"EmailService logger name: {email_service.logger.name}")
    print(f"NotificationService logger name: {notification_service.logger.name}")

    result = notification_service.notify_user_created("bob", "bob@example.com")
    print(f"Result: {result}")

    print("\n4. Factory function with automatic logger:")
    print("-" * 40)

    # Get the audit message - the factory function should also get a logger
    audit_message = injector.produce(injector.plan(planner_input)).get(str, "audit")
    print(f"Audit result: {audit_message}")

    print("\n5. Manual logger vs automatic logger:")
    print("-" * 40)

    # Compare manual and automatic logger
    manual_service = injector.produce(injector.plan(planner_input)).get(ManualLoggerService)
    print(f"Manual logger name: {manual_service.logger.name}")
    manual_result = manual_service.do_something()
    print(f"Manual result: {manual_result}")

    # Get another database service to show automatic logger
    auto_db = injector.produce(injector.plan(planner_input)).get(DatabaseService)
    print(f"Automatic logger name: {auto_db.logger.name}")
    auto_result = auto_db.query("SELECT * FROM users")
    print(f"Auto result: {auto_result}")

    print("\n6. Function injection with automatic logger:")
    print("-" * 40)

    def business_logic(
        database: DatabaseService, email: EmailService, logger: logging.Logger
    ) -> str:
        logger.info("Running business logic")
        db_result = database.query("SELECT COUNT(*) FROM users")
        email_result = email.send_email("admin@example.com", "Daily Report")
        logger.info("Business logic completed")
        return f"Business completed: {db_result}, {email_result}"

    # Use produce_run to inject dependencies into the function
    business_result = injector.produce_run(planner_input, business_logic)
    print(f"Business result: {business_result}")

    print("\n7. Logger name patterns:")
    print("-" * 40)

    # Show the pattern of logger names
    services = [
        ("DatabaseService", injector.produce(injector.plan(planner_input)).get(DatabaseService)),
        ("UserService", injector.produce(injector.plan(planner_input)).get(UserService)),
        ("EmailService", injector.produce(injector.plan(planner_input)).get(EmailService)),
        (
            "NotificationService",
            injector.produce(injector.plan(planner_input)).get(NotificationService),
        ),
    ]

    for service_name, service in services:
        logger_name = service.logger.name
        print(f"{service_name:20} -> Logger: {logger_name}")

    print("\nDemo completed successfully!")
    print("\nKey points:")
    print("- Loggers are automatically injected for 'logging.Logger' dependencies without names")
    print("- Logger names are based on the location where they're requested")
    print("- Named logger dependencies (using @Id) are NOT auto-injected")
    print("- Each service gets its own appropriately named logger")
    print("- No manual logger setup is required!")


if __name__ == "__main__":
    main()
