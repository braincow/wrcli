#!/usr/bin/env python3

import click
import sys
import logging
import time
import json

import asyncio
import serial.aio

class RecordInterface(asyncio.Protocol):
    def __init__(self, reset_interface, output_file):
        super()
        self.reset_interface = reset_interface
        self.output_file = output_file
        self.record = { 'write': dict(), 'read': dict() }

    def write(self, message):
        logging.debug("sending data %s" % message)
        self.record["write"][time.time()] = message.decode('UTF-8').strip()
        self.transport.write(message)

    def connection_made(self, transport):
        self.transport = transport
        logging.debug("port opened %s" % self.transport)
        self.write(b'USB\r\n')
        if self.reset_interface:
            self.write(b'RESET\r\n')
        self.write(b'IV?\r\n')

    def data_received(self, data):
        logging.debug('data received %s' % repr(data))
        self.record["read"][time.time()] = data.decode('UTF-8').strip()

    def end_session(self):
        self.transport.close()
        self.output_file.write(json.dumps(self.record, sort_keys=True, indent=4, separators=(',', ': ')))

@click.group()
@click.option('--tty', required=True, default="/dev/ttyACM0", type=click.Path(exists=True), help="TTY device for accessing Water Rower USB interface")
@click.option('--baudrate', required=True, default=115200, help="Baudrate used when communicating with the Water Rower USB interface")
@click.option('--debug/--no-debug', is_flag=True, default=False, help="Enable more verbose output from execution")
@click.pass_context
def cli(ctx, baudrate, tty, debug):
    """
    Water Rower USB interface command line client
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(module)s] [%(levelname)s] %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(module)s] [%(levelname)s] %(message)s')
    
    ctx.obj["tty"] = tty
    ctx.obj["baudrate"] = baudrate

@cli.command()
@click.option('--reset/--no-reset', is_flag=True, default=True, help="Reset rowing computer on initiating communication")
@click.argument('output', required=True, type=click.File('w'))
@click.pass_context
def record(ctx, reset, output):
    """
    Record rowing computer inputs and outputs in json format as they happen. End session with ctrl+c
    """
    interface = RecordInterface(reset_interface=reset, output_file=output)
    loop = asyncio.get_event_loop()
    coro = serial.aio.create_serial_connection(loop,
        lambda: interface,
        ctx.obj["tty"], baudrate=ctx.obj["baudrate"])
    loop.run_until_complete(coro)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        interface.end_session()
    loop.close()

# start client as main program
def main():
    # init cli interface and start it
    cli(obj=dict())
    sys.exit(0)

if __name__ == '__main__':
    main()

# eof