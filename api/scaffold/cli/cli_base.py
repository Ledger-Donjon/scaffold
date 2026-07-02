import argparse

import serial.tools.list_ports
from rich.console import Console
from rich_argparse import RichHelpFormatter

from scaffold import Scaffold

from .cli_atecc import CLI_ATECC
from .cli_iso7816 import CLI_ISO7816
from .cli_uart import CLI_UART

class CLI_BASE:
    """Command Line Interface for interacting with the Scaffold."""

    DIGITAL_IO = ["d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7"]

    def __init__(self, scaffold: Scaffold | None, console: Console):
        self.console = console
        self.scaffold = scaffold
        self.parser = CLI_BASE.create_parser()

    @staticmethod
    def create_parser():
        """Create the argument parser for the CLI."""
        parser = argparse.ArgumentParser(
            prog="scaffold", formatter_class=RichHelpFormatter
        )
        parser.add_argument(
            "--dev",
            help="Select scaffold device (optional)",
            default=None,
            required=False,
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        # scaffold list
        subparsers.add_parser(
            "list", help="List available boards", formatter_class=RichHelpFormatter
        )

        # scaffold version
        subparsers.add_parser(
            "version",
            help="Show version information",
            formatter_class=RichHelpFormatter,
        )

        # scaffold reset
        subparsers.add_parser(
            "reset",
            help="Reset the scaffold (including I/Os)",
            formatter_class=RichHelpFormatter,
        )

        # scaffold power dut/platform/all on/off
        power_parser = subparsers.add_parser(
            "power", help="Control power", formatter_class=RichHelpFormatter
        )
        power_parser.add_argument(
            "target", choices=["dut", "platform", "all"], help="Power target"
        )
        power_parser.add_argument("state", choices=["on", "off"], help="Power state")
        power_parser.add_argument(
            "--trigger",
            help="Optional trigger for power control",
            choices=CLI_BASE.DIGITAL_IO,
            default=None,
            required=False,
        )

        # scaffold d0/d1/d2/d3/d4/d5 on/off
        d_parser = subparsers.add_parser(
            "io", help="Control I/Os", formatter_class=RichHelpFormatter
        )
        d_parser.add_argument("line", choices=CLI_BASE.DIGITAL_IO, help="I/O line")
        d_parser.add_argument("state", choices=["high", "low"], help="Line state")
        
        # scaffold atecc [commands]
        CLI_ATECC.create_parser(subparsers)
        # scaffold iso7816 [commands]
        CLI_ISO7816.create_parser(subparsers)
        # scaffold uart [commands]
        CLI_UART.create_parser(subparsers)
        
        return parser

    def handle_power(self, args: argparse.Namespace) -> None:
        """
        Handle the 'power' command to control power to DUT, platform, or all.

        :param args: Parsed command-line arguments.
        :type args: argparse.Namespace
        """
        assert self.scaffold is not None
        
        if args.trigger:
            _ = getattr(self.scaffold, args.trigger) << self.scaffold.power.dut_trigger

        value = 1 if args.state == "on" else 0
        if args.target in ["dut", "platform"]:
            setattr(self.scaffold.power, args.target, value)
        elif args.target == "all":
            self.scaffold.power.all = 0b11 if value else 0b00

        trigger_msg = ""
        if args.trigger:
            trigger_msg += "[green] with trigger on [/green]"
            trigger_msg += f"[bold yellow]{args.trigger}[/bold yellow]"
        self.console.print(
            "[green]Power [/green]"
            f"[bold yellow]{args.target}[/bold yellow]"
            "[green] set to [/green]"
            f"[bold yellow]{args.state}[/bold yellow]"
            f"{trigger_msg}"
        )

    def handle_io(self, args: argparse.Namespace) -> None:
        """
        Handle the 'io' command to control digital I/O lines.

        :param args: Parsed command-line arguments.
        :type args: argparse.Namespace
        """
        value = 1 if args.state == "high" else 0
        _ = getattr(self.scaffold, args.line) << value
        self.console.print(
            "[green]I/O [/green]"
            f"[bold yellow]{args.line}[/bold yellow]"
            "[green] set to [/green]"
            f"[bold yellow]{args.state}[/bold yellow]"
        )

    def handle_version(self) -> None:
        """
        Handle the 'version' command to display the Scaffold version.
        """
        assert self.scaffold is not None
        self.console.print(
            "[green]Scaffold version: [/green]"
            f"[bold yellow]{self.scaffold.version}[/bold yellow]"
        )

    def handle_reset(self) -> None:
        """
        Handle the 'reset' command to reset the Scaffold board.
        This includes resetting all I/O lines.
        """
        assert self.scaffold is not None
        self.scaffold.reset_config(init_ios=True)
        self.console.print("[green]Scaffold board reset successfully.[/green]")

    def handle_list(self) -> None:
        """
        Handle the 'list' command to list available Scaffold devices.
        """
        found = False
        for port in serial.tools.list_ports.comports():
            if port.product is not None and port.product.lower() == "scaffold":
                self.console.print(
                    "[green]Found device: [/green]"
                    f"[bold yellow]{port.device}[/bold yellow]"
                    f"[green] - {port.description} ({port.hwid})[/green]"
                )
                found = True
        if not found:
            self.console.print("[red]No scaffold devices found.[/red]")
