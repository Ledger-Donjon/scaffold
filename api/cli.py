import argparse
import serial.tools.list_ports

from scaffold import Scaffold


class CLI:
    DIGITAL_IO = ["d0", "d1", "d2", "d3", "d4", "d5"]

    def __init__(self):
        self.scaffold = None
        self.parser = self.parse()

    def parse(self):
        parser = argparse.ArgumentParser(prog="scaffold")
        parser.add_argument("--dev", help="Select scaffold device (optional)", default=None, required=False)
        subparsers = parser.add_subparsers(dest="command", required=True)

        # scaffold list
        subparsers.add_parser("list", help="List available board")

        # scaffold version
        subparsers.add_parser("version", help="Show version information")

        # scaffold power dut/platform/all on/off
        power_parser = subparsers.add_parser("power", help="Control power")
        power_parser.add_argument("target", choices=["dut", "platform", "all"], help="Power target")
        power_parser.add_argument("state", choices=["on", "off"], help="Power state")
        power_parser.add_argument(
            "--trigger",
            help="Optional trigger for power control",
            choices=self.DIGITAL_IO,
            default=None,
            required=False
        )

        # scaffold d0/d1/d2/d3/d4/d5 on/off
        d_parser = subparsers.add_parser("io", help="Control I/Os")
        d_parser.add_argument("line", choices=self.DIGITAL_IO, help="I/O line")
        d_parser.add_argument("state", choices=["on", "off"], help="Line state")

        # scaffold uart
        uart_parser = subparsers.add_parser("uart", help="UART interactive shell")
        uart_parser.add_argument("rx", choices=self.DIGITAL_IO, help="RX I/O line")
        uart_parser.add_argument("tx", choices=self.DIGITAL_IO, help="TX I/O line")
        uart_parser.add_argument("--baudrate", type=int, default=9600, help="UART baudrate (default: 9600)")

        # scaffold apdu
        iso7816_parser = subparsers.add_parser("iso7816", help="ISO 7816 interface")
        iso7816_subparsers = iso7816_parser.add_subparsers(dest="iso7816_command", required=True)

        # iso7816 apdu <hexstr>
        apdu_parser = iso7816_subparsers.add_parser("apdu", help="Send APDU command")
        apdu_parser.add_argument("hexstr", help="APDU command as hex string")

        # iso7816 reset
        iso7816_subparsers.add_parser("reset", help="Reset ISO 7816 interface")

        return parser

    def handle_power(self, args):
        if args.trigger:
            getattr(self.scaffold, args.trigger) << self.scaffold.power.dut_trigger

        value = 1 if args.state == "on" else 0
        if args.target in ["dut", "platform"]:
            setattr(self.scaffold.power, args.target, value)
        elif args.target == "all":
            self.scaffold.power.all = 0b11 if value else 0b00
        print(f"Power {args.target} set to {args.state}{' with trigger on' if args.trigger else ''}")

    def handle_io(self, args):
        value = 1 if args.state == "on" else 0
        # line is sanitized by argparse choice
        getattr(self.scaffold, args.line) << value
        print(f"{args.line} set to {args.state}")

    def handle_version(self):
        print(f"Scaffold version: {self.scaffold.version}")

    def handle_list(self, args):
        for port in serial.tools.list_ports.comports():
            if port.product is not None and port.product.lower() == "scaffold":
                print(f"{port.device} - {port.description} ({port.hwid})")

    def handle_uart(self, args):
        print(f"Starting UART shell on RX: {args.rx}, TX: {args.tx}, Baudrate: {args.baudrate}")
        uart = self.scaffold.uart0
        uart.baudrate = args.baudrate

        # rx/tx are sanitized by argparse choice
        getattr(self.scaffold, args.tx) << uart.tx
        uart.rx << getattr(self.scaffold, args.rx)

        uart.flush()
        print("Press Ctrl+C to leave the UART shell.")
        try:
            while True:
                data = input(">> ")
                if data:
                    uart.transmit(data.encode())
                response = uart.receive()
                if response:
                    print(f"Received: {response.decode(errors='replace')}")
        except KeyboardInterrupt:
            pass

    def handle_iso7816(self, args):
        iso7816 = Smartcard(self.scaffold)

        if args.iso7816_command == "apdu":
            print(f"Sending APDU: {args.hexstr}")
            apdu_bytes = bytes.fromhex(args.hexstr)
            response = iso7816.transmit(apdu_bytes)
            print(f"Response: {response.hex()}")
        elif args.iso7816_command == "reset":
            print("Resetting card interface and retrieving ATR...")
            atr = iso7816.reset()
            print(f"ATR: {atr.hex() if atr else 'No ATR received'}")

    def run(self):
        args = self.parser.parse_args()

        # List does not require a device
        if args.command == "list":
            self.handle_list(args)
            return

        # Instantiate Scaffold
        if args.dev is None:
            self.scaffold = Scaffold()
        else:
            self.scaffold = Scaffold(dev=args.dev)
    
        if args.command == "power":
            self.handle_power(args)
        elif args.command == "io":
            self.handle_io(args)
        elif args.command == "version":
            self.handle_version()
        elif args.command == "uart":
            self.handle_uart(args)
        elif args.command == "apdu":
            self.handle_apdu(args)

def main() -> None:
    CLI().run()

if __name__ == "__main__":
    main()