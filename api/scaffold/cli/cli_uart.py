from __future__ import annotations

import signal
import argparse
from rich.console import Console
from rich.prompt import Prompt
from rich_argparse import RichHelpFormatter

from scaffold import Scaffold
from scaffold.bus import TimeoutError

class UARTPrompt(Prompt):
    """Custom prompt for UART communication."""

    prompt_suffix = ""
    
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


class CLI_UART:
    DIGITAL_IO = ["d0", "d1", "d2", "d3", "d4", "d5"]
    
    def __init__(self, scaffold: Scaffold | None, console: Console):
        self.scaffold = scaffold
        self.console = console

    @staticmethod
    def create_parser(subparsers: argparse._SubParsersAction) -> None:
        """
        Create the parser for the 'uart' command.
        """
        # scaffold uart
        uart_parser = subparsers.add_parser(
            "uart", help="UART interactive shell", formatter_class=RichHelpFormatter
        )
        uart_parser.add_argument(
            "rx", choices=CLI_UART.DIGITAL_IO, help="RX I/O line (required)"
        )
        uart_parser.add_argument(
            "tx", choices=CLI_UART.DIGITAL_IO, help="TX I/O line (required)"
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
            type=float,
            default=1,
            help="UART timeout in seconds (default: 1)",
        )
        uart_parser.add_argument(
            "--buffer",
            type=int,
            default=1,
            help="UART buffer size in bytes (default: 1)",
        )
        uart_parser.add_argument(
            "--hex",
            action="store_true",
            help="Treat input as hex string, and show response as hex (default: false)",
        )
        
    def handle_uart(self, args: argparse.Namespace) -> None:
        """
        Handle the 'uart' command to start an interactive UART shell
        or retrieve UART logs.

        :param args: Parsed command-line arguments.
        :type args: argparse.Namespace
        """
        assert self.scaffold is not None
        
        if args.rx == args.tx:
            self.console.print("[red]Error: RX and TX lines cannot be the same.[/red]")
            return

        self.console.print(
            "[green]Initializing UART with RX: [/green]"
            f"[bold yellow]{args.rx}[/bold yellow]"
            "[green], TX: [/green]"
            f"[bold yellow]{args.tx}[/bold yellow]"
            "[green], Baudrate: [/green]"
            f"[bold yellow]{args.baudrate}[/bold yellow]"
            "[green], Timeout: [/green]"
            f"[bold yellow]{args.timeout}[/bold yellow]"
        )
        self.scaffold.timeout = args.timeout

        uart = self.scaffold.uart0
        uart.baudrate = args.baudrate
        _ = uart.rx << getattr(self.scaffold, args.rx)
        _ = getattr(self.scaffold, args.tx) << uart.tx

        uart.flush()
        
        if args.mode == "log":
            self.console.print("[blue]Entering UART log mode. "
                               "Press Ctrl+C to exit.[/blue]")
            try:
                response = b""
                while True:
                    try:
                        with DelayedKeyboardInterrupt():
                            response += uart.receive(args.buffer)
                    except TimeoutError:
                        response_str = (response.hex() if args.hex else response.decode(errors='replace'))
                        self.console.print(f"{response_str}")
                        self.console.print(
                            "[blue]UART log mode exited (reason: timeout).[/blue]"
                        )
                        break
                    if b"\n" in response:
                        response_str = (response.hex() if args.hex else response.decode(errors='replace'))
                        self.console.print(f"{response_str}")
                        response = b""
            except KeyboardInterrupt:
                self.console.print("[blue]UART log mode exited (reason: user).[/blue]")
        elif args.mode == "repl":
            self.console.print(
                "[blue]Entering UART REPL mode. " + \
                ("Hex input is expected. " if args.hex else "ASCII input is expected.") + \
                "Press Ctrl+C to leave the UART shell.[/blue]"
            )
            try:
                while True:
                    data = UARTPrompt.ask("[green]uart> [/green]")
                    if data:
                        if args.hex:
                            try:
                                data_bytes = bytes.fromhex(data)
                            except ValueError:
                                self.console.print("[red]Invalid hex string.[/red]")
                                continue
                        else:
                            data_bytes = data.encode()
                        uart.transmit(data_bytes)
                    response = b""
                    try:
                        while True:
                            with DelayedKeyboardInterrupt():
                                response += uart.receive(args.buffer)
                    except TimeoutError:
                        pass
                    if response:
                        response_str = (response.hex() if args.hex else response.decode(errors='replace'))
                        self.console.print(f"{response_str}")
            except KeyboardInterrupt:
                self.console.print("[blue]UART shell exited (reason: user).[/blue]")
