from packet import Packet
import random
import time
from queue import Queue
import threading
import argparse
import socket
from concurrent.futures import ThreadPoolExecutor, process
from asyncio_socket import recvfrom, sendto
import asyncio

# initialize to dumby values for sanity checking purposes
max_delay = None # max delay a packet can be delayed by in milliseconds

forward_recv_port = None # the port to listen on to get messages from the sender
backward_recv_port = None # emulator's receiving UDP port from receiver

receiver_addr = None # receiver's network address
receiver_recv_port = None # receiver's receiving UDP port

sender_addr = None # sender's network address
sender_recv_port = None # the sender's receiving UDP port number

prob_discard = None # the probability a packet is discarded

verbose = False

data_buff = Queue()
ack_buff = Queue()


async def processPacket(packet, fromSender):
    loop = asyncio.get_event_loop()
    global prob_discard
    if not isinstance(packet, bytes):
        raise RuntimeError("processPacket can only process a packet encoded as bytes")
    recvd_packet = Packet(packet)
    typ, seqnum, length, data = recvd_packet.decode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False) 
    if verbose: print("Packet being processed: Type={}, seqnum={}, length={}, data={}".format(typ, seqnum, length, data))
    if typ == 2: # if type == EOT
        if fromSender:
            while not data_buff.empty():
                # delay for longest possible delay and check again.
                await delay_async_io(max_delay)
            if verbose: print("Sending packet: Type={}, seqnum={}, length={}, data={}".format(typ, seqnum, length, data))
            await sendto(loop, sock, packet, (receiver_addr, receiver_recv_port))
        else:
            while not ack_buff.empty():
                # delay for longest possible delay and check again.
                await delay_async_io(max_delay)
            if verbose: print("Sending packet: Type={}, seqnum={}, length={}, data={}".format(typ, seqnum, length, data))
            await sendto(loop, sock, packet, (sender_addr, sender_recv_port))
    else:
        if not randomTrue(prob_discard):
            # process packet
            if fromSender:
                if typ == 0:
                    raise RuntimeError("Received an Ack from the sender")
                    pass
                if verbose: print("Adding packet to data buffer: Type={}, seqnum={}, length={}, data={}".format(typ, seqnum, length, data))
                data_buff.put(packet)
            else:
                if typ == 1:
                    raise RuntimeError("Received data from the receiver")
                if verbose: print("Adding packet to ack buffer: Type={}, seqnum={}, length={}, data={}".format(typ, seqnum, length, data))
                ack_buff.put(packet)
            delay = random.randint(0, max_delay)
            await delay_async_io(delay)
            if fromSender:
                data_buff.get(block=False)
            else:
                ack_buff.get(block=False)
            if verbose: print("Sending packet: Type={}, seqnum={}, length={}, data={}".format(typ, seqnum, length, data))         
            if fromSender:
                await sendto(loop, sock, packet, (receiver_addr, receiver_recv_port))
            else:
                await sendto(loop, sock, packet, (sender_addr, sender_recv_port))
        else:
            if verbose: print("Dropped packet: Type={}, seqnum={}, length={}, data={}".format(typ, seqnum, length, data))



async def forwardFlow():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    sock.bind(("", forward_recv_port))
    loop = asyncio.get_event_loop()
    while True:
        packet, addr = await recvfrom(loop, sock, 1024)
        if verbose: print("Received a packet from from sender")
        loop.run_until_complete(asyncio.ensure_future(processPacket(packet, True)))

async def backwardFlow():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    sock.bind(("", backward_recv_port))
    loop = asyncio.get_event_loop()
    while True:
        packet, addr = await recvfrom(loop, sock, 1024)
        if verbose: print("Received a packet from from client")
        loop.run_until_complete(asyncio.ensure_future(processPacket(packet, False)))

async def delay_async_io(delay):
    # need to convert milliseconds to seconds for time.sleep()
    s_delay = delay / 1000.0
    if verbose: print("Packet delayed by {} milliseconds".format(delay))
    await asyncio.sleep(s_delay)



def randomTrue(probability):
    return random.random() < probability

async def main():
    forward = asyncio.ensure_future(forwardFlow())
    backward = asyncio.ensure_future(backwardFlow())
    await asyncio.gather(forward, backward, return_exceptions=False)

if __name__ == '__main__':
    # Parse args
    parser = argparse.ArgumentParser()
    parser.add_argument("<Forward receiving port>", help="emulator's receiving UDP port number in the forward (sender) direction")
    parser.add_argument("<Receiver's network address>")
    parser.add_argument("<Reciever’s receiving UDP port number>")
    parser.add_argument("<Backward receiving port>", help="emulator's receiving UDP port number in the backward (receiver) direction")
    parser.add_argument("<Sender's network address>")
    parser.add_argument("<Sender's receiving UDP port number>")
    parser.add_argument("<Maximum Delay>", help="maximum delay of the link in units of millisecond")
    parser.add_argument("<drop probability>", help="packet discard probability")
    parser.add_argument('<verbose>', nargs='?', default=0)
    args = parser.parse_args()
    # set up sockets to be listening on
    args = args.__dict__ # A LAZY FIX
    max_delay = int(args["<Maximum Delay>"])
    forward_recv_port = int(args["<Forward receiving port>"])
    backward_recv_port = int(args["<Backward receiving port>"])
    receiver_addr = str(args["<Receiver's network address>"])
    receiver_recv_port = int(args["<Reciever’s receiving UDP port number>"])
    sender_addr = str(args["<Sender's network address>"])
    sender_recv_port = int(args["<Sender's receiving UDP port number>"])
    prob_discard = float(args["<drop probability>"])
    if prob_discard < 0 or prob_discard > 1:
        raise RuntimeError("Probability of discarding a packet should be between 0 and 1")

    verbose = (1 == int(args["<verbose>"]))

    # start a thread for both forward and backword network flow
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())