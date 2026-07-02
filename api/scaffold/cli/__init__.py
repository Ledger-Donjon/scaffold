from serial.serialutil import SerialException

from rich.console import Console

from .cli_base import CLI_BASE, Scaffold
from .cli_atecc import CLI_ATECC
from .cli_iso7816 import CLI_ISO7816
from .cli_uart import CLI_UART

class CLI(CLI_BASE, CLI_ATECC, CLI_ISO7816, CLI_UART):
    def __init__(self):
        self.scaffold: Scaffold | None = None
        self.console = Console()
        CLI_BASE.__init__(self, self.scaffold, self.console)
        CLI_ATECC.__init__(self, self.scaffold, self.console)
        CLI_ISO7816.__init__(self, self.scaffold, self.console)
        CLI_UART.__init__(self, self.scaffold, self.console)

    def run(self) -> None:
        """
        Parse command-line arguments, instantiate a scaffold object if needed
        and dispatch to the appropriate handler.
        """
        args = self.parser.parse_args()

        if args.command == "list":
            self.handle_list()
            return

        try:
            if args.dev is None:
                self.console.print(
                    "[yellow]No device specified, "
                    "using default Scaffold device.[/yellow]"
                )
                self.scaffold = Scaffold()
            else:
                self.console.print(
                    "[yellow]Using Scaffold device: [/yellow]"
                    f"[bold yellow]{args.dev}[/bold yellow]"
                )
                self.scaffold = Scaffold(dev=args.dev)
        except (RuntimeError, SerialException):
            self.console.print(
                "[red]Error: Unable to connect to the specified Scaffold device.[/red]"
            )
            return

        if args.command == "power":
            self.handle_power(args)
        elif args.command == "io":
            self.handle_io(args)
        elif args.command == "version":
            self.handle_version()
        elif args.command == "uart":
            self.handle_uart(args)
        elif args.command == "iso7816":
            self.handle_iso7816(args)
        elif args.command == "atecc":
            self.handle_atecc(args)
        elif args.command == "reset":
            self.handle_reset()

def main() -> None:
    CLI().run()


if __name__ == "__main__":
    main()
