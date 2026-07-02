import argparse
from time import sleep
from scaffold.atecc import ATECC, Config, ATECCZone, ATECCOpCode
from scaffold import Scaffold
from rich.console import Console
from rich_argparse import RichHelpFormatter
import yaml
from scaffold.atecc import ATECC, ATECCInterface

class CLI_ATECC:
    def __init__(self, scaffold: Scaffold | None, console: Console):
        self.scaffold = scaffold
        self.console = console
        
    @staticmethod
    def create_parser(subparsers: argparse._SubParsersAction) -> None:
        """Create the argument parser for the CLI."""
        parser = argparse.ArgumentParser(
            prog="scaffold", formatter_class=RichHelpFormatter
        )
        
        # atecc
        atecc_parser = subparsers.add_parser(
            "atecc", help="ATECC Wizard", formatter_class=RichHelpFormatter
        )
        atecc_subparsers = atecc_parser.add_subparsers(
            dest="atecc_command", required=True
        )

        atecc_parser.add_argument(
            "--interface",
            choices=ATECCInterface,
            default=ATECCInterface.I2C,
            help="Interface to use for the ATECC (default: i2c)",
        )
        atecc_parser.add_argument(
            "--address",
            type=int,
            default=ATECC.DEFAULT_ADDRESS,
            help="I2C address of the ATECC (default: 0xC0)",
        )
        
        # trigger
        atecc_parser.add_argument(
            "--trigger",
            action="store_true",
            help="Trigger the ATECC",
        )

        # atecc config
        atecc_config_parser = atecc_subparsers.add_parser(
            "config",
            help="Configuration of the ATECC",
            formatter_class=RichHelpFormatter,
        )
        atecc_config_parser.add_argument(
            "--read",
            action="store_true",
            help="Read the configuration of the ATECC",
        )
        atecc_config_parser.add_argument(
            "--write",
            action="store_true",
            help="Write the configuration to the ATECC",
        )
        atecc_config_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Dry run mode. Configuration will not be written to the ATECC.",
        )
        atecc_config_parser.add_argument(
            "-i", "--in-bin", type=argparse.FileType("rb"), help="Read configuration from binary file"
        )
        atecc_config_parser.add_argument(
            "-y", "--in-yaml", type=argparse.FileType("r"), help="Read configuration from yaml file"
        )
        atecc_config_parser.add_argument(
            "-o", "--out-bin", type=argparse.FileType("wb"), help="Save whole configuration as binary file."
        )
        atecc_config_parser.add_argument(
            "-z", "--out-yaml", type=argparse.FileType("w"), help="Save whole configuration as yaml file."
        )
        
        # atecc slot and key
        atecc_config_parser.add_argument(
            "--slot",
            type=int,
            help="Slot index",
            choices=range(16),
            required=False,
        )
        atecc_config_parser.add_argument(
            "--key",
            type=int,
            help="Key index",
            choices=range(16),
            required=False,
        )
        
        # atecc gen priv key
        atecc_gen_priv_key_parser = atecc_subparsers.add_parser(
            "gen-priv-key",
            help="Generate a private key with the ATECC",
            formatter_class=RichHelpFormatter,
        )
        atecc_gen_priv_key_parser.add_argument(
            "--slot", type=int, help="Slot index")
        
        # atecc gen pub key
        atecc_gen_pub_key_parser = atecc_subparsers.add_parser(
            "gen-pub-key",
            help="Generate a public key with the ATECC",
            formatter_class=RichHelpFormatter,
        )
        atecc_gen_pub_key_parser.add_argument(
            "--slot", type=int, help="Slot index")
        
        # atecc sign
        atecc_sign_parser = atecc_subparsers.add_parser(
            "sign",
            help="Sign a message with the ATECC",
            formatter_class=RichHelpFormatter,
        )
        atecc_sign_parser.add_argument(
            "--key", type=int, help="Key index", required=True)
        
        # atecc nonce
        atecc_nonce_parser = atecc_subparsers.add_parser(
            "nonce",
            help="Generate a nonce with the ATECC",
            formatter_class=RichHelpFormatter,
        )
        atecc_nonce_parser.add_argument(
            "--update-seed",
            action="store_true",
            help="Update the seed of the ATECC",
        )
        return atecc_config_parser

    def handle_atecc(self, args: argparse.Namespace) -> None:
        """
        Handle the 'atecc' command to interact with the ATECC chip.
        """
        assert self.scaffold is not None
        
        # Initialize the ATECC chip.
        atecc = ATECC(self.scaffold, interface=args.interface)
        if atecc.interface == ATECCInterface.I2C:
            atecc.address = args.address
        elif args.interface == ATECCInterface.SWI:
            self.console.print("[red]Setting I2C address for SWI interface is not relevant.[/red]")
        
        try:
            atecc.wake_up()        
            if args.atecc_command == "config":
                if args.read:
                    config = atecc.read_config()
                    self.console.print(
                        "[green]Interface: [/green]"
                        f"[bold yellow]{args.interface}[/bold yellow]"
                        "[green], Address: [/green]"
                        f"[bold yellow]0x{args.address:02X}[/bold yellow]"
                    )
                    
                    
                    if args.slot is not None:
                        config.print_slot_config(
                            slot_config=config.slot_config[args.slot],
                            slot_index=args.slot,
                            print=self.console.print,
                        )
                    elif args.key is not None:
                        config.print_key_config(
                            key_config=config.key_config[args.key],
                            key_index=args.key,
                            print=self.console.print,
                        )
                    else:
                        config.print_config(print=self.console.print)
                        
                    if args.out_yaml is not None:
                        try:
                            yaml.dump(config.to_yaml(), args.out_yaml)
                            self.console.print(f"[green]Configuration saved to yaml file {args.out_yaml.name}.[/green]")
                        except Exception as e:
                            self.console.print(f"[red]Error saving configuration to yaml file {args.out_yaml.name}: {e}[/red]")
                        finally:
                            args.out_yaml.close()
                    
                    if args.out_bin is not None:
                        try:
                            args.out_bin.write(config.raw)
                            self.console.print(f"[green]Configuration saved to binary file {args.out_bin.name}.[/green]")
                        except Exception as e:
                            self.console.print(f"[red]Error saving configuration to binary file {args.out_bin.name}: {e}[/red]")
                        finally:
                            args.out_bin.close()
                            
                if args.write:
                    config = Config()
                    if args.in_bin is not None:
                        config.from_bytes(args.in_bin.read(), 0)
                        args.in_bin.close()
                    elif args.in_yaml is not None:
                        config.from_yaml(yaml.safe_load(args.in_yaml))
                        args.in_yaml.close()
                    else:
                        self.console.print("[red]No configuration file provided.[/red]")
                        return
                    
                    self.console.print("[green]Configuration to be written:[/green]")
                    config.print_config(print=self.console.print)
                    
                    if args.dry_run:
                        self.console.print("[green]Dry run mode enabled. Configuration will not be written to the ATECC. Exiting...[/green]")
                        return
                    
                    for i in range(16, 128, 4):
                        if (i >= 84) and (i < 90):
                            continue
                        data = config.raw[i : i + 4]
                        block = i // 32
                        offset = (i - block * 32) // 4
                        atecc.wake_up()
                        atecc.write(data, zone=ATECCZone.CONFIG, block=block, offset=offset)
                        atecc.idle()
                    self.console.print("[green]Configuration written to the ATECC.[/green]")
                    
            elif args.atecc_command == "gen-priv-key":
                priv = atecc.gen_priv_key(args.slot, trigger=args.trigger)
                self.console.print(f"[green]Private key: {priv.hex()}[/green]")
            elif args.atecc_command == "gen-pub-key":
                pub = atecc.gen_pub_key(args.slot, trigger=args.trigger)
                self.console.print(f"[green]Public key: {pub.hex()}[/green]")
            elif args.atecc_command == "sign":
                # signature = atecc.sign(args.key, trigger=args.trigger)
                print(atecc.command(ATECCOpCode.SIGN, 0, args.key, trigger=args.trigger))
                self.console.print(f"[green]Signature: {signature.hex()}[/green]")
            elif args.atecc_command == "nonce":
                random_data = atecc.nonce(update_seed=args.update_seed)
                self.console.print(f"[green]Random data: {random_data.hex()}[/green]")
            
            try:
                atecc.idle()
            except Exception as t:
                self.console.print(f"[orange3]Warning: Failed to idle the ATECC: {t}[/orange3]")
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")