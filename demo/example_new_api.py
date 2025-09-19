#!/usr/bin/env python3
"""
Example demonstrating the new PlannerInput-based API that matches the original distage library.
"""

from typing import Annotated

from izumi.distage import Id, Injector, ModuleDef, PlannerInput
from izumi.distage.model import DIKey


class Database:
    def __init__(self, connection_string: str = "default-connection"):
        self.connection_string = connection_string

    def query(self, sql: str) -> str:
        return f"Executing '{sql}' on {self.connection_string}"


class UserService:
    def __init__(self, database: Database):
        self.database = database

    def get_user(self, user_id: int) -> str:
        return self.database.query(f"SELECT * FROM users WHERE id = {user_id}")


def main():
    # Define the module with bindings
    module = ModuleDef()
    module.make(Database).using().type(Database)
    module.make(UserService).using().type(UserService)

    # Create PlannerInput - this is immutable and contains all configuration
    planner_input = PlannerInput([module])

    # Create stateless Injector
    injector = Injector()

    # Option 1: Create a Plan and use Locator (explicit control)
    print("=== Option 1: Plan + Locator ===")
    plan = injector.plan(planner_input)
    locator = injector.produce(plan)

    # Get individual services
    user_service = locator.get(DIKey.of(UserService))
    result1 = user_service.get_user(123)
    print(f"Result 1: {result1}")

    # Option 2: Use produce_run for function-based injection (recommended)
    print("\n=== Option 2: Function-based injection ===")

    def my_application(user_service: UserService, database: Database) -> str:
        user_data = user_service.get_user(456)
        db_info = database.query("SELECT COUNT(*) FROM users")
        return f"User: {user_data}, Total users: {db_info}"

    result2 = injector.produce_run(planner_input, my_application)
    print(f"Result 2: {result2}")

    # Option 3: Multiple Locators from same Plan (different instances)
    print("\n=== Option 3: Multiple Locators ===")
    locator1 = injector.produce(plan)
    locator2 = injector.produce(plan)

    db1 = locator1.get(DIKey.of(Database))
    db2 = locator2.get(DIKey.of(Database))

    print(f"Database 1 ID: {id(db1)}")
    print(f"Database 2 ID: {id(db2)}")
    print(f"Different instances: {db1 is not db2}")

    # Option 4: Using PlannerInput utility methods
    print("\n=== Option 4: PlannerInput utilities ===")
    targeted_input = PlannerInput.target([module], UserService)
    targeted_plan = injector.plan(targeted_input)
    print(f"Targeted plan keys: {list(targeted_plan.keys())}")

    # Option 5: Named dependencies with Id annotations
    print("\n=== Option 5: Named Dependencies ===")

    class ConfigurableService:
        def __init__(
            self,
            api_key: Annotated[str, Id("api-key")],
            timeout: Annotated[int, Id("timeout")],
            database: Database,  # Regular dependency
        ):
            self.api_key = api_key
            self.timeout = timeout
            self.database = database

        def make_api_call(self) -> str:
            return f"API call with key '{self.api_key}' (timeout: {self.timeout}s) to {self.database.connection_string}"

    # Create a new module with named bindings
    named_module = ModuleDef()
    named_module.make(Database).using().type(Database)
    named_module.make(str).named("api-key").using().value("prod-api-key-123")
    named_module.make(int).named("timeout").using().value(30)
    named_module.make(ConfigurableService).using().type(ConfigurableService)

    named_input = PlannerInput([named_module])
    locator = injector.produce(injector.plan(named_input))
    service = locator.get(DIKey.of(ConfigurableService))
    print(f"Named dependency result: {service.make_api_call()}")

    # Demonstrate accessing named dependencies directly
    api_key = locator.get(DIKey.of(str, "api-key"))
    timeout = locator.get(DIKey.of(int, "timeout"))
    print(f"Direct access - API Key: {api_key}, Timeout: {timeout}")


if __name__ == "__main__":
    main()
