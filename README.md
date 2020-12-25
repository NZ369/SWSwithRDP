# SoR Server
## Simple Web Server (SWS) with Reliable Datagram Protocol (RDP) Transceiver

#### Creation of a simple web server (SWS) framework following the HTTP protocol to transfer files through reliable datagram protocol (RDP) implemented via UDP.

#### Server side transfers a file requested by the client through a customly created RDP connection.  The file requested will be transferred correctly and rapidly regardless of internet delay or loss.  Error control, flow control, and fast retransmission are implemented.  

#### Packet format:
RDP-COMMAND<br>
RDP-Header: Value
…
RDP-Header: Value
HTTP-COMMAND
HTTP-Header: Value
…. 
HTTP-Header: Value
HTTP-PAYLOAD

#### To establish the RDP connection and send the HTTP request: 
“  
SYN|DAT|ACK. 
Sequence: 0. 
Length: 48. 
Acknowledgment: -1. 
Window: 4096. 
GET /sws.py HTTP/1.0. 
Connection: keep-alive. 
“  

SoR is bidirectional with data flows between the SoR client and server for request-response applications, but unlike the TCP socket, SoR has the flexibility to establish the RDP connection and send the HTTP request in one packet. If the RDP-PAYLOAD is longer than what SoR can accommodate, RST is triggered to reset the connection, and the user can rerun the SoR client with a smaller RDP-PAYLOAD size.  

HTTP packet PAYLOAD is at most 1024 bytes, so if requested file is much longer than 1024 bytes, requested file will be segmented into multiple HTTP-PAYLOAD segments encapsulated in many RDP packets, regulated by RDP flow and error control.

Either SoR client or server can first close the RDP connection by sending an RDP packet containing the FIN command, and the connection is fully closed after the other party’s FIN command is acknowledged, so in an ideal case for a small enough request and response, SoR can finish the transaction in 1 RTT and 3 packets.

#### How to run SoR server:
*python3 sor-server.py server_ip_address server_udp_port_number server_buffer_size server_payload_length

On server, where the SoR server binds to server_ip_address and server_udp_port for RDP, with server_buffer_size for each RDP connection to receive data, and server_payload_length to send data.

#### How to run SoR client:
*python3 sor-client.py server_ip_address server_udp_port_number client_buffer_size client_payload_length read_file_name write_file_name [read_file_name write_file_name]*

On client, where the SoR client connects to the SoR server at server_ip_address and server_udp_port, with client_buffer_size for each RDP connection to receive data, and client_payload_length to send data, and requests the file with read_file_name from the SoR server on H1 and writes to write_file_name on H1.

If there are multiple pairs of read_file_name and write_file_name in the command line, it indicates that the SoR client shall request these files from the SoR server in a persistent HTTP session over an RDP connection.
