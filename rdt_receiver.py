from packet import Packet
import sys
import socket

last_ack = -1 # The seqnum of the last (latest) acknowledged packet
buffer = [] # Buffer for storing out-of-order data packets

# Default values for hosts, ports and output file name
self_host = "localhost"
emu_host = "localhost"
self_port = 12345
emu_port = 54321
writefile_name = "out.txt" # Output to this file

buf_size = 1024 * 2 # max buffer size of the UDP Socket
max_window_size = 10
mod = 32

if len(sys.argv)-1 != 4:
        print("Incorrect number of command line arguments!")
        print("Please provide <emulator_host_address> <emulator_recv_port>, " \
        "<receiver_port> and <outputfile_name>!")
        sys.exit()

emu_host = sys.argv[1]
emu_port = int(sys.argv[2])
self_port = int(sys.argv[3])
writefile_name = sys.argv[4]
with open(writefile_name, "w") as wf:
        wf.write("")

self_addr = (self_host, self_port)
emu_addr = (emu_host, emu_port)
# Condition operator for seqnum since there is modulo
# earlier_than(31, 1) = True ; earlier_than (15,17) = True
# earlier_than(2, 28) = False; earlier_than (21, 23) = False
def earlier_than(l, r):
    if (l<max_window_size) and (r>=l-max_window_size+mod):
        return False;
    if (r<max_window_size) and (l>=r-max_window_size+mod):
        return True;
    return l <= r;

# Function to determine of a data packet received is within the next 10 seqnums
def not_in_window_range(l, r):
    if (r<max_window_size) and (l>=r-max_window_size+mod):
        return False;
    if (r - l > 10):
        return True;
    return False;

# Main function
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_s:
    udp_s.bind(self_addr) # Initialize a UDP socket
    # Initialize an arrival.log
    with open("arrival.log", "w") as f:
        f.write("")

    # Run a loop until an EOT Packet is received
    while True:
        # Wait until a packet is received, no timeouts
        data, addr = udp_s.recvfrom(buf_size)
        packet = Packet(data)
        if (not packet) or (not packet.typ):
            continue

        # If we see an EOT
        if packet.typ == 2:
            udp_s.sendto(Packet(2, 0, 0, "").encode(), emu_addr) # Send back an EOT
            sys.exit()

        # If we receive a data packet; In principle, the receiver cannot receive any acknowledgements
        elif packet.typ == 1:
            with open("arrival.log", "a") as f:
                f.write(f"{packet.seqnum}\n") # Log the seqnum of the incoming packet
            # Just send the latest acknowledged seqnum back if the incoming packet is outdated
            if (earlier_than(packet.seqnum, last_ack)):
                udp_s.sendto(Packet(0, last_ack, 0, "").encode(), emu_addr)
            # Just send the latest acknowledged seqnum back if the incoming packet is not within the next 10 seqnum
            elif not_in_window_range(last_ack, packet.seqnum):
                udp_s.sendto(Packet(0, last_ack, 0, "").encode(), emu_addr)
            # Incoming packet's seqnum is what we are looking for, no need to place in buffer
            elif (packet.seqnum == (last_ack + 1) % mod):
                # Update latest acknowlegement
                last_ack += 1
                last_ack %= mod
                with open(writefile_name, "a") as wf:
                    wf.write(packet.data) # Write data to file
                udp_s.sendto(Packet(0, last_ack, 0, "").encode(), emu_addr) # Send back updated acknowlegement

                # Iterate through buffer; acknowlege, write and remove all those that can be acknowledged
                while True:
                    flag = False
                    temp = None
                    for b in buffer:
                        if (b.seqnum == (last_ack + 1) % mod):
                            last_ack += 1
                            last_ack %= mod
                            with open(writefile_name, "a") as wf:
                                wf.write(b.data)
                            udp_s.sendto(Packet(0, last_ack, 0, "").encode(), emu_addr)
                            temp = b
                            flag = True
                            break

                    if (not flag):
                        break
                    else:
                        buffer.remove(temp)

            # Place out of order packet in buffer
            else:
                # Cannot place in buffer if the buffer is full
                if (len(buffer) < max_window_size):
                    isAlreadyIn = False
                    # Check if the packet is already in the buffer; if not, place it in
                    for b in buffer:
                        if (b.seqnum == packet.seqnum):
                            isAlreadyIn = True
                            break
                    if (not isAlreadyIn):
                        buffer.append(packet)
                # Send latest acknowlegement, although it is unchanged in this scenario
                udp_s.sendto(Packet(0, last_ack, 0, "").encode(), emu_addr)
