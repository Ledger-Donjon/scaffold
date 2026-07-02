import argparse
from rich.console import Console
from rich_argparse import RichHelpFormatter
from scaffold import Scaffold
from scaffold.iso7816 import Smartcard

class CLI_ISO7816:
    def __init__(self, scaffold: Scaffold | None, console: Console):
        self.scaffold = scaffold
        self.console = console

    @staticmethod
    def create_parser(subparsers: argparse._SubParsersAction) -> None:
        """
        Create the parser for the 'iso7816' command.
        """

        # scaffold iso7816
        iso7816_parser = subparsers.add_parser(
            "iso7816", help="ISO 7816 interface", formatter_class=RichHelpFormatter
        )
        iso7816_subparsers = iso7816_parser.add_subparsers(
            dest="iso7816_command", required=True
        )

        # iso7816 apdu <hexstr>
        apdu_parser = iso7816_subparsers.add_parser(
            "apdu", help="Send APDU command", formatter_class=RichHelpFormatter
        )
        apdu_parser.add_argument("hexstr", help="APDU command as hex string")
        apdu_parser.add_argument(
            "--trigger",
            help="Optional trigger for power control",
            choices=["d4", "d5"],
            default=None,
            required=False,
        )

        # iso7816 reset
        iso7816_subparsers.add_parser(
            "reset", help="Reset ISO 7816 interface", formatter_class=RichHelpFormatter
        )

    def handle_iso7816(self, args: argparse.Namespace) -> None:
        """
        Handle the 'iso7816' command to interact with ISO 7816 smartcards.

        :param args: Parsed command-line arguments.
        :type args: argparse.Namespace
        """
        assert self.scaffold is not None
        
        sm = Smartcard(self.scaffold)

        # Always reset the card interface before sending
        # commands (so reset command does nothing more)
        self.console.print("[green]Resetting card interface and retrieving ATR...[/green]")
        atr = sm.reset()
        self.console.print(
            "[green]ATR: [/green]"
            f"[bold yellow]{atr.hex() if atr else 'No ATR received'}[/bold yellow]"
        )

        if args.iso7816_command == "apdu":
            if args.trigger:
                _ = getattr(self.scaffold, args.trigger) << sm.iso7816.trigger

            trigger_msg = ""
            if args.trigger:
                trigger_msg = "[green] with [/green]"
                trigger_msg += "[bold yellow]ab[/bold yellow]"
                trigger_msg += "[green] trigger on [/green]"
                trigger_msg += f"[bold yellow]{args.trigger}[/bold yellow]"
            self.console.print(
                "[green]Sending APDU [/green]"
                f"[bold yellow]{args.hexstr}[/bold yellow]"
                f"{trigger_msg}"
            )
            response = sm.apdu(args.hexstr, trigger="ab" if args.trigger else "")
            self.console.print(
                f"[green]Response: [/green][bold yellow]{response.hex()}[/bold yellow]"
            )
