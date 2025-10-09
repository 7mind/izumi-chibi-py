import logging

from izumi.distage import Injector, Lifecycle, ModuleDef, PlannerInput


class DBConnection:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connected = False

    def connect(self) -> None:
        print(f"[DB] Connecting to {self.connection_string}")
        self.connected = True

    def disconnect(self) -> None:
        print(f"[DB] Disconnecting from {self.connection_string}")
        self.connected = False

    def query(self, sql: str) -> str:
        assert self.connected, "Not connected to database"
        return f"Result: {sql}"


class MessageQueue:
    def __init__(self):
        self.connected = False

    def connect(self) -> None:
        print("[MQ] Connecting to message queue")
        self.connected = True

    def disconnect(self) -> None:
        print("[MQ] Disconnecting from message queue")
        self.connected = False

    def send(self, message: str) -> None:
        assert self.connected, "Not connected to message queue"
        print(f"[MQ] Sending: {message}")


class UserService:
    def __init__(self, db: DBConnection, mq: MessageQueue, logger: logging.Logger):
        self.db = db
        self.mq = mq
        self.logger = logger

    def create_user(self, name: str) -> str:
        self.logger.info(f"Creating user: {name}")
        result = self.db.query(f"INSERT INTO users (name) VALUES ('{name}')")
        self.mq.send(f"User created: {name}")
        return result


def db_lifecycle(connection_string: str) -> Lifecycle[DBConnection]:
    """Create a lifecycle-managed database connection."""

    def acquire() -> DBConnection:
        conn = DBConnection(connection_string)
        conn.connect()
        return conn

    def release(conn: DBConnection) -> None:
        conn.disconnect()

    return Lifecycle.make(acquire, release)


def mq_lifecycle() -> Lifecycle[MessageQueue]:
    """Create a lifecycle-managed message queue connection."""

    def acquire() -> MessageQueue:
        mq = MessageQueue()
        mq.connect()
        return mq

    def release(mq: MessageQueue) -> None:
        mq.disconnect()

    return Lifecycle.make(acquire, release)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Lifecycle Demo ===\n")
    print("1. Creating module with lifecycle-managed resources...")
    print("-" * 50)

    module = ModuleDef()
    module.make(str).using().value("postgresql://localhost:5432/mydb")
    module.make(DBConnection).using().fromResource(db_lifecycle("postgresql://localhost:5432/mydb"))
    module.make(MessageQueue).using().fromResource(mq_lifecycle())
    module.make(UserService).using().type(UserService)

    injector = Injector()
    planner_input = PlannerInput([module])

    print("\n2. Running application (resources will be acquired)...")
    print("-" * 50)

    def app(service: UserService) -> str:
        print("\n[APP] Inside application logic")
        result1 = service.create_user("alice")
        result2 = service.create_user("bob")
        print("[APP] Application logic completed\n")
        return f"{result1}, {result2}"

    # Resources are automatically acquired and released
    result = injector.produce_run(planner_input, app)

    print("\n3. Resources have been automatically released!")
    print("-" * 50)
    print(f"\nFinal result: {result}")
    print("\nDemo completed successfully!")
