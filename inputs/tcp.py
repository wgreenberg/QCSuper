#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from socket import socket, AF_INET, SOCK_STREAM

try:
    from os import setpgrp
except ImportError:
    setpgrp = None

from inputs._hdlc_mixin import HdlcMixin
from inputs._base_input import BaseInput

"""
    This class implements reading Qualcomm DIAG data from a the /dev/diag
    character device, on a remote Android device connected through ADB.
    
    For this, it uploads the C program located in "./adb_bridge/" which
    creates a TCP socket acting as a proxy to /dev/diag.
"""

class TcpConnector(HdlcMixin, BaseInput):
    
    def __init__(self, host, port):
        self._disposed = False
        self.packet_buffer = b''
        self.socket = socket(AF_INET, SOCK_STREAM)
        try:
            self.socket.connect((host, port))
        except Exception as e:
            print(e)
            exit(f'Could not connect to {host}:{port}. Is the server running?')
        self.received_first_packet = False
        super().__init__()
    
    
    def send_request(self, packet_type, packet_payload):
        raw_payload = self.hdlc_encapsulate(bytes([packet_type]) + packet_payload)
        self.socket.send(raw_payload)
    
    def read_loop(self):
        while True:
            while self.TRAILER_CHAR not in self.packet_buffer:
                # Read message from the TCP socket
                socket_read = self.socket.recv(1024 * 1024 * 10)
                
                if not socket_read:
                    print('\nThe connection to the TCP bridge was closed, or ' +
                        'preempted by another QCSuper instance')
                    return
                
                self.packet_buffer += socket_read
            
            while self.TRAILER_CHAR in self.packet_buffer:
                # Parse frame
                raw_payload, self.packet_buffer = self.packet_buffer.split(self.TRAILER_CHAR, 1)
                
                # Decapsulate and dispatch
                try:
                    unframed_message = self.hdlc_decapsulate(
                        payload = raw_payload + self.TRAILER_CHAR,
                        raise_on_invalid_frame = not self.received_first_packet
                    )
                
                except self.InvalidFrameError:
                    # The first packet that we receive over the Diag input may
                    # be partial
                    continue
                
                finally:
                    self.received_first_packet = True
                
                self.dispatch_received_diag_packet(unframed_message)

    def dispose(self, disposing=True):
        if not self._disposed:
            self.socket.close()
            self._disposed = True
