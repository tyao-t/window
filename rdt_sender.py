from packet import Packet
import sys
import socket
import time

last_ack = -1 # The seqnum of the last (latest) acknowledged packet

# Default values for hosts and ports
self_host = "localhost"
emu_host = "localhost"
self_port = 34343
emu_port = 43434

if len(sys.argv)-1 != 5:
        print("Incorrect number of command line arguments!")
        print("Please provide <emulator_host_address> <emulator_send_port>, " \
            "<sender_port>, <timeout_value> and <inputfile_name>!")
        sys.exit()

emu_host = sys.argv[1]
emu_port = int(sys.argv[2])
self_port = int(sys.argv[3])
time_out = int(sys.argv[4]) # in milliseconds
readfile_name = sys.argv[5] # read from this file

self_addr = (self_host, self_port)
emu_addr = (emu_host, emu_port)
chunk_size = 500 # length (chunk size) of data in each packet
mod = 32
max_window_size = 10

seqnum = 0 # counter for the seqnums of packets
buf_size = 1024 * 2 # max buffer size of the UDP Socket
timestamp = 0

# populate data from file
packet_data = []
with open(readfile_name, "r") as rf:
    while True:
        data = rf.read(chunk_size)
        if (not data) or (data == ""):
            break
        packet_data.append(data)

packets = []
# generate data packets
for data in packet_data:
    packets.append(Packet(1, seqnum, len(data), data))
    seqnum += 1
    seqnum %= mod

socket.setdefaulttimeout(0)

# Condition operator for seqnum since there is modulo
# earlier_than(31, 1) = True ; earlier_than (15,17) = True
# earlier_than(2, 28) = False; earlier_than (21, 23) = False
def earlier_than(l, r):
    if (l<max_window_size) and (r>=l-max_window_size+mod):
        return False;
    if (r<max_window_size) and (l>=r-max_window_size+mod):
        return True;
    return l <= r;

#Main function
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_s:
    udp_s.bind(self_addr) #Initialize a UDP socket
    window = []
    N = 1 # Size of window
    # Initialize ack.log, seqnum.log, and N.log
    with open("ack.log", "w") as ackl:
        ackl.write("")
    with open("seqnum.log", "w") as sl:
        sl.write("")
    with open("N.log", "w") as nl:
        nl.write(f"t={timestamp} 1\n")
        timestamp += 1

    # Keep running as long as there are still packets remaining
    while (len(packets) > 0):
        idx = 0
        # During each iteration (round), if the window isn't full, we populate it first
        while (len(window) < N) and (idx < len(packets)):
            window.append(packets[idx])
            idx += 1

        start_time = None # timer variable
        for i in range(len(window)):
            udp_s.sendto(window[i].encode(), emu_addr)
            if (i == 0):
                start_time = time.time() # start counting when we send the first packet is sent
            with open("seqnum.log", "a") as sl:
                sl.write(f"t={timestamp} {window[i].seqnum}\n") # log the sent packet's seqnum
                timestamp += 1

        got_ack = False # flag to keep track of whether or not we get at least one valid acknowledgement this round
        # Keep listening for acknowledgements
        while True:
            if (time.time() - start_time)*1000 > time_out:
                break # Quit loop if timed out, timestamp increased later when packet is re-sent

            try:
                resp, addr = udp_s.recvfrom(buf_size)
            except:
                pass # Got no ack just yet
            else:
                resp_pkt = Packet(resp) # Receives an acknowledgement
                # Check if the acknowledgement is outdated or duplicate
                if earlier_than(last_ack, resp_pkt.seqnum):
                    # If not duplicate
                    if (last_ack != resp_pkt.seqnum):
                        got_ack = True
                        with open("ack.log", "a") as nl:
                            nl.write(f"t={timestamp} {resp_pkt.seqnum}\n")
                            timestamp += 1
                        last_ack = resp_pkt.seqnum
                        break # Stop listening for ACK


        # If we don't receive any valid acknowledgement, reset window size to 1 and log changes, if there's any
        if (not got_ack):
            with open("N.log", "a") as nl:
                nl.write(f"t={timestamp} 1\n")
            N = 1
            window = [] # Retransmission is done at the next iteration of the main loop (round), which is equivalent, since N is reset to 1.
        # If we do receive at least one valid acknowlegement
        else:
            N += 1 # Increase N by 1
            if (N > 10):
                N = 10 # Make sure N is at most 10
            with open("N.log", "a") as nl:
                nl.write(f"t={timestamp} {N}\n")
            # Remove all packets (that are acknowledged) from the window and from the original list
            while (men(window) > 0) and (earlier_than(window[0].seqnum, last_ack)):
                window.pop(0)
            while (len(packets) > 0) and (earlier_than(packets[0].seqnum, last_ack)):
                packets.pop(0)

    udp_s.sendto(Packet(2, 0, 0, "").encode(), emu_addr) # Send EOT packet
    # Log EOT
    with open("seqnum.log", "a") as sl:
        sl.write(f"t={timestamp} EOT\n")
        timestamp += 1
    # Wait for EOT packet from receiver
    while True:
        try:
            eot, addr = udp_s.recvfrom(buf_size)
        except:
            pass
        # Shut down the program if EOT from receiver is seen
        else:
            if (Packet(eot).typ == 2):
                with open("ack.log", "a") as ackl:
                    ackl.write(f"t={timestamp} EOT\n")
                    timestamp += 1
                sys.exit()
