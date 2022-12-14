import asyncio
import logging
from functools import partial

from .client import ChainLink
from .utils import make_header


logger = logging.getLogger(__name__)


class RingManager:
    """ Manages a ring of peers.

        All peers are connected to each other in a ring and instanced on localhost.
    """
    def __init__(self, loop=None) -> None:
        if loop is None:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop=loop
        
        self.reset()

    def reset(self):
        """ Clears the peer list. """
        self.peers = {}

    def cancel_all(self):
        """ Cancel all peers and futures, then reset the manager. """

        for peer, future in zip(self.peers.values(), self.futures.values()):
            peer.close()
            future.cancel()

        self.reset()

    def add_peer(self, future, peer, addr) -> None:
        logger.debug("Adding peer %s", addr)
        self.peers[addr] = (peer, future)

    async def build(self, hosts):
        for addr in hosts:
            server_finished = self.loop.create_future()
            peer = await self.loop.create_server(
                ChainLink.factory(server_finished, {'addr': addr}), addr[0], addr[1], ssl=None
            )

            self.add_peer(server_finished, peer, addr)

    async def connect(self, a1, a2):
        """ Connects two peers together using an ad-hoc connection. """
        transport, _ = await self.loop.create_connection(
            ChainLink.factory(None, None), a1[0], a1[1]
        )

        transport.write(make_header(*a2))
        transport.close()

    async def connect_peer_ring(self):
        """ Connect all peers in the ring together. """
        logger.debug("Connecting peers")
        for a1, a2 in zip(self.peers.keys(), list(self.peers.keys())[1:]):
            if a1 == a2:
                continue
            # Loopback
            if a2 is None:
                a2 = self.peers[0][0]

            logger.debug("Connecting %s to %s", a1, a2)
            await self.connect(a1, a2)

    async def run(self):
        """ Connect and start the ring. """
        logger.debug("Starting ring manager")
        await self.connect_peer_ring()

        futures = asyncio.gather(*[peer[1] for peer in self.peers.values()])
        await futures