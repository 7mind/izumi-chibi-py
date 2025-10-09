import logging

from izumi.distage import EntrypointArgs, ModuleDef, RoleAppMain, RoleTask


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

    module = ModuleDef()
    module.makeRole(HelloTask)
    module.makeRole(GoodbyeTask)

    app = RoleAppMain()
    app.add_module(module)
    app.main()
