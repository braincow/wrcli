#!/usr/bin/env python3

# loosely based on https://github.com/gar3thjon3s/rower

import click
import sys
import logging
import time
import json

import asyncio
import serial.aio

class RecordInterface(asyncio.Protocol):
    def __init__(self, reset_interface, record_pulse, record_ping, output_file):
        super()
        self.reset_interface = reset_interface
        self.record_pulse = record_pulse
        self.record_ping = record_ping
        self.output_file = output_file
        self.record = { 'write': dict(), 'read': dict() }

    def write(self, message):
        logging.debug("sending data %s" % message)
        self.record["write"][time.time() - self.start_time] = message.decode('UTF-8').strip()
        self.transport.write(message)

    def connection_made(self, transport):
        logging.info("Starting recording from rowing computer")
        self.start_time = time.time()
        self.transport = transport
        logging.debug("port opened %s" % self.transport)
        self.write(b'USB\r\n')
        if self.reset_interface:
            self.write(b'RESET\r\n')
        self.write(b'IV?\r\n')

    def data_received(self, data):
        logging.debug('data received %s' % repr(data))
        data = data.decode('UTF-8').strip()
        if data == "PING" and not self.record_ping:
            # do not record PING messages unless specified
            return
        if data[:1] == "P" and not self.record_pulse:
            # return empty and exit quietly as we do not want to record pulse messages
            return
        if data == "SS":
            logging.info("Store started")
        if data == "SE":
            logging.info("Stroke ended")
            # stroke has ended
            # Requests the contents of a single location XXX, this will return a single byte in hex format.  
            self.write(b'IRS055\r\n') # total_distanse_m
            self.write(b'IRS1A9\r\n') # strokerate
            self.write(b'IRS140\r\n') # total_strokes
            # Returns the single byte of data Y1 from location XXX for the users application.
            #self.write("IDS")
        # add row to recording
        self.record["read"][time.time() - self.start_time] = data

    def end_session(self):
        self.transport.close()
        # restructure the recording to include more information
        read = self.record["read"]
        write = self.record["write"]
        self.record = dict()
        self.record["00_header"] = { "recording": { "start": self.start_time, "end": time.time() }}
        self.record["01_data"] = { "01_read": read, "00_write": write }
        self.output_file.write(json.dumps(self.record, sort_keys=True, indent=4, separators=(',', ': ')))

@click.group()
@click.option('--tty', required=True, default="/dev/ttyACM1", type=click.Path(exists=True), help="TTY device for accessing Water Rower USB interface")
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
@click.option('--pulse/--no-pulse', is_flag=True, default=False, help="Record intensity pulse")
@click.option('--ping/--no-ping', is_flag=True, default=False, help="Record idle ping messages")
@click.argument('output', required=True, type=click.File('w'))
@click.pass_context
def record(ctx, reset, pulse, ping, output):
    """
    Record rowing computer inputs and outputs in json format as they happen. End session with ctrl+c
    """
    interface = RecordInterface(reset_interface=reset, record_pulse=pulse, record_ping=ping, output_file=output)
    loop = asyncio.get_event_loop()
    coro = serial.aio.create_serial_connection(loop,
        lambda: interface,
        ctx.obj["tty"], baudrate=ctx.obj["baudrate"])
    loop.run_until_complete(coro)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt")
    finally:
        logging.info("Ending recording session.")
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