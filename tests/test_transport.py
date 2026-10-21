import json
import os
import socket
import sys
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from E2PVR.transport import WebSocket


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client, self.server=socket.socketpair()
        self.client.settimeout(1)
        self.server.settimeout(1)
        self.ws=WebSocket("example.test.token")
        self.ws.sock=self.client

    def tearDown(self):
        self.ws.close()
        self.server.close()

    def test_client_masks_utf8_json(self):
        self.ws.send_json({"text":"سلام"})
        packet=self.server.recv(4096)
        self.assertEqual(packet[0],0x81)
        self.assertTrue(packet[1]&0x80)
        size=packet[1]&0x7f
        mask=packet[2:6]
        decoded=bytes(value^mask[index%4] for index,value in enumerate(packet[6:6+size]))
        self.assertEqual(json.loads(decoded),{"text":"سلام"})

    def test_ping_and_fragmented_server_json(self):
        first=b'{"ready":'
        second=b'true}'
        self.server.sendall(b'\x89\x01p'+bytes([0x01,len(first)])+first+bytes([0x80,len(second)])+second)
        opcode, message=self.ws.recv_message()
        self.assertEqual(opcode,1)
        self.assertEqual(json.loads(message),{"ready":True})
        pong=self.server.recv(256)
        self.assertEqual(pong[0],0x8a)

    def test_masked_server_frames_are_rejected(self):
        self.server.sendall(b'\x81\x81abcdx')
        with self.assertRaisesRegex(IOError,"masked server"):
            self.ws.recv_message()


if __name__ == "__main__":
    unittest.main()
