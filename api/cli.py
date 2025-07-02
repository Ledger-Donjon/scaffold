import argparse
import signal

import serial.tools.list_ports
from rich.console import Console
from rich.prompt import Prompt

from scaffold import Scaffold
from scaffold.iso7816 import Smartcard
from scaffold.bus import TimeoutError

console = Console()


# Context manager from https://stackoverflow.com/a/21919644
class DelayedKeyboardInterrupt:
    """Context manager to delay KeyboardInterrupt handling.
    This is used to define a critical section when interacting with scaffold.
    """

    def __enter__(self):
        self.signal_received = False
        self.old_handler = signal.signal(signal.SIGINT, self.handler)

    def handler(self, sig, frame):
        self.signal_received = (sig, frame)

    def __exit__(self, type, value, traceback):
        signal.signal(signal.SIGINT, self.old_handler)
        if self.signal_received:
            self.old_handler(*self.signal_received)


class UARTPrompt(Prompt):
    """Custom prompt for UART communication."""

    prompt_suffix = ""


class CLI:
    """Command Line Interface for interacting with the Scaffold."""

    DIGITAL_IO = ["d0", "d1", "d2", "d3", "d4", "d5"]

    def __init__(self):
        self.scaffold = None
        self.parser = self.create_parser()

    def create_parser(self):
        """Create the argument parser for the CLI."""
        parser = argparse.ArgumentParser(prog="scaffold")
        parser.add_argument(
            "--dev",
            help="Select scaffold device (optional)",
            default=None,
            required=False,
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        # scaffold list
        subparsers.add_parser("list", help="List available board")

        # scaffold version
        subparsers.add_parser("version", help="Show version information")

        # scaffold power dut/platform/all on/off
        power_parser = subparsers.add_parser("power", help="Control power")
        power_parser.add_argument(
            "target", choices=["dut", "platform", "all"], help="Power target"
        )
        power_parser.add_argument("state", choices=["on", "off"], help="Power state")
        power_parser.add_argument(
            "--trigger",
            help="Optional trigger for power control",
            choices=self.DIGITAL_IO,
            default=None,
            required=False,
        )

        # scaffold d0/d1/d2/d3/d4/d5 on/off
        d_parser = subparsers.add_parser("io", help="Control I/Os")
        d_parser.add_argument("line", choices=self.DIGITAL_IO, help="I/O line")
        d_parser.add_argument("state", choices=["on", "off"], help="Line state")

        # scaffold uart
        uart_parser = subparsers.add_parser("uart", help="UART interactive shell")
        uart_parser.add_argument(
            "rx", choices=self.DIGITAL_IO, help="RX I/O line (required)"
        )
        uart_parser.add_argument(
            "tx", choices=self.DIGITAL_IO, help="TX I/O line (required)"
        )
        uart_parser.add_argument(
            "--baudrate", type=int, default=9600, help="UART baudrate (default: 9600)"
        )
        uart_parser.add_argument(
            "--mode",
            choices=["log", "repl"],
            default="log",
            help="UART mode (default: log)",
        )
        uart_parser.add_argument(
            "--timeout",
            type=int,
            default=1,
            help="UART timeout in seconds (default: 1)",
        )
        uart_parser.add_argument(
            "--buffer",
            type=int,
            default=1,
            help="UART buffer size in bytes (default: 1)",
        )

        # scaffold iso7816
        iso7816_parser = subparsers.add_parser("iso7816", help="ISO 7816 interface")
        iso7816_subparsers = iso7816_parser.add_subparsers(
            dest="iso7816_command", required=True
        )

        # iso7816 apdu <hexstr>
        apdu_parser = iso7816_subparsers.add_parser("apdu", help="Send APDU command")
        apdu_parser.add_argument("hexstr", help="APDU command as hex string")
        apdu_parser.add_argument(
            "--trigger",
            help="Optional trigger for power control",
            choices=["d4", "d5"],
            default=None,
            required=False,
        )

        # iso7816 reset
        iso7816_subparsers.add_parser("reset", help="Reset ISO 7816 interface")

        return parser

    def handle_power(self, args: argparse.Namespace) -> None:
        """
        Handle the 'power' command to control power to DUT, platform, or all.

        :param args: Parsed command-line arguments.
        :type args: argparse.Namespace
        """
        if args.trigger:
            getattr(self.scaffold, args.trigger) << self.scaffold.power.dut_trigger

        value = 1 if args.state == "on" else 0
        if args.target in ["dut", "platform"]:
            setattr(self.scaffold.power, args.target, value)
        elif args.target == "all":
            self.scaffold.power.all = 0b11 if value else 0b00
        console.print(
            f"[green]Power [/green][bold yellow]{args.target}[/bold yellow][green] set to [/green]"
            f"[bold yellow]{args.state}[/bold yellow]"
            f"{f'[green] with trigger on [/green][bold yellow]{args.trigger}[/bold yellow]' if args.trigger else ''}"
        )

    def handle_io(self, args: argparse.Namespace) -> None:
        """
        Handle the 'io' command to control digital I/O lines.

        :param args: Parsed command-line arguments.
        :type args: argparse.Namespace
        """
        value = 1 if args.state == "on" else 0
        getattr(self.scaffold, args.line) << value
        console.print(
            f"[bold yellow]{args.line}[/bold yellow][green] set to [/green][bold yellow]{args.state}[/bold yellow]"
        )

    def handle_version(self) -> None:
        """
        Handle the 'version' command to display the Scaffold version.
        """
        console.print(
            f"[green]Scaffold version: [/green][bold yellow]{self.scaffold.version}[/bold yellow]"
        )

    def handle_list(self) -> None:
        """
        Handle the 'list' command to list available Scaffold devices.
        """
        found = False
        for port in serial.tools.list_ports.comports():
            if port.product is not None and port.product.lower() == "scaffold":
                console.print(
                    f"[green]Found device: [/green][bold yellow]{port.device}[/bold yellow]"
                    f"[green] - {port.description} ({port.hwid})[/green]"
                )
                found = True
        if not found:
            console.print("[red]No scaffold devices found.[/red]")

    def handle_uart(self, args: argparse.Namespace) -> None:
        """
        Handle the 'uart' command to start an interactive UART shell or retrieve UART logs.

        :param args: Parsed command-line arguments.
        :type args: argparse.Namespace
        """
        if args.rx == args.tx:
            console.print("[red]Error: RX and TX lines cannot be the same.[/red]")
            return

        console.print(
            f"[green]Initializing UART on RX: [/green][bold yellow]{args.rx}[/bold yellow]"
            f"[green], TX: [/green][bold yellow]{args.tx}[/bold yellow]"
            f"[green], Baudrate: [/green][bold yellow]{args.baudrate}[/bold yellow]"
            f"[green], Timeout: [/green][bold yellow]{args.timeout}[/bold yellow]"
        )
        self.scaffold.timeout = args.timeout

        uart = self.scaffold.uart0
        uart.baudrate = args.baudrate
        uart.rx << getattr(self.scaffold, args.rx)
        getattr(self.scaffold, args.tx) << uart.tx

        uart.flush()

        if args.mode == "log":
            console.print("[blue]Entering UART log mode. Press Ctrl+C to exit.[/blue]")
            try:
                response = b""
                while True:
                    try:
                        with DelayedKeyboardInterrupt():
                            response += uart.receive(args.buffer)
                    except TimeoutError:
                        console.print(f"{response.decode(errors='replace')}")
                        console.print(
                            "[blue]UART log mode exited (reason: timeout).[/blue]"
                        )
                        break
                    if b"\n" in response:
                        console.print(f"{response.decode(errors='replace')}")
                        response = b""
            except KeyboardInterrupt:
                console.print("[blue]UART log mode exited (reason: user).[/blue]")
        elif args.mode == "repl":
            console.print(
                "[blue]Entering UART REPL mode. Press Ctrl+C to leave the UART shell.[/blue]"
            )
            try:
                while True:
                    data = UARTPrompt.ask("[green]uart> [/green]")
                    if data:
                        uart.transmit(data.encode())
                    response = b""
                    try:
                        while True:
                            with DelayedKeyboardInterrupt():
                                response += uart.receive(args.buffer)
                    except TimeoutError:
                        pass
                    if response:
                        console.print(f"{response.decode(errors='replace')}")
            except KeyboardInterrupt:
                console.print("[blue]UART shell exited (reason: user).[/blue]")

    def handle_iso7816(self, args: argparse.Namespace) -> None:
        """
        Handle the 'iso7816' command to interact with ISO 7816 smartcards.

        :param args: Parsed command-line arguments.
        :type args: argparse.Namespace
        """
        sm = Smartcard(self.scaffold)

        # Always reset the card interface before sending commands (so reset command does nothing more)
        console.print("[green]Resetting card interface and retrieving ATR...[/green]")
        atr = sm.reset()
        console.print(
            f"[green]ATR: [/green][bold yellow]{atr.hex() if atr else 'No ATR received'}[/bold yellow]"
        )

        if args.iso7816_command == "apdu":
            if args.trigger:
                getattr(self.scaffold, args.trigger) << sm.iso7816.trigger
            console.print(
                f"[green]Sending APDU [/green][bold yellow]{args.hexstr}[/bold yellow]"
                f"{f'[green] with [/green][bold yellow]ab[/bold yellow][green] trigger on [/green][bold yellow]{args.trigger}[/bold yellow]' if args.trigger else ''}"
            )
            response = sm.apdu(args.hexstr, trigger="ab" if args.trigger else "")
            console.print(
                f"[green]Response: [/green][bold yellow]{response.hex()}[/bold yellow]"
            )

    def run(self) -> None:
        """
        Parse command-line arguments, instantiate a scaffold object if needed and dispatch to the appropriate handler.
        """
        args = self.parser.parse_args()

        if args.command == "list":
            self.handle_list()
            return

        try:
            if args.dev is None:
                console.print(
                    "[yellow]No device specified, using default Scaffold device.[/yellow]"
                )
                self.scaffold = Scaffold()
            else:
                console.print(
                    f"[yellow]Using Scaffold device: [/yellow][bold yellow]{args.dev}[/bold yellow]"
                )
                self.scaffold = Scaffold(dev=args.dev)
        except (RuntimeError, serial.serialutil.SerialException):
            console.print(
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


def main() -> None:
    CLI().run()


if __name__ == "__main__":
    main()
