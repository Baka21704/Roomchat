import socket
import logging
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

HOST = '0.0.0.0'
PORT = 12345
BUFFER_SIZE = 1024
MAX_WORKERS = 20


logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# clients: map socket -> {'addr': (host,port), 'name': str}
clients = {}
clients_lock = Lock()


def broadcast(message: bytes, source_conn=None):
    """Send `message` to all connected clients except `source_conn`.

    Removes clients that fail during send.
    """
    # Take a snapshot to avoid holding the lock while sending
    with clients_lock:
        conns = list(clients.items())  # list of (conn, info)

    for conn, info in conns:
        if conn is source_conn:
            continue
        try:
            conn.sendall(message)
        except Exception:
            logger.exception('Failed to send to %s, removing client', info.get('addr'))
            try:
                conn.close()
            except Exception:
                pass
            with clients_lock:
                clients.pop(conn, None)


def handle_client(conn, addr):
    """Handle a single client: register, receive messages and broadcast them.

    Protocol: the first line sent by the client is treated as the username.
    Subsequent lines are broadcast to other clients prefixed with the sender's name.
    """
    logger.info('Accepted connection from %s', addr)

    # Wrap socket with a file-like object for line-oriented reading
    fileobj = conn.makefile('r', encoding='utf-8', newline='\n')
    name = None
    try:
        # Read username (first line)
        first = fileobj.readline()
        if not first:
            return
        name = first.rstrip('\n').strip() or f"{addr[0]}:{addr[1]}"

        # Register client with name
        with clients_lock:
            clients[conn] = {'addr': addr, 'name': name}

        logger.info('Registered %s for %s', name, addr)

        # Read subsequent lines and broadcast (supports /nick command)
        for line in fileobj:
            text = line.rstrip('\n')
            if not text:
                continue

            # Handle nickname change command: /nick newname
            if text.startswith('/nick '):
                newname = text[len('/nick '):].strip() or name
                oldname = name
                name = newname
                with clients_lock:
                    info = clients.get(conn)
                    if info:
                        info['name'] = name

                notice = f"{oldname} is now known as {name}\n".encode('utf-8')
                # Broadcast notice to everyone (including the requester)
                broadcast(notice, source_conn=None)
                continue

            payload_text = f"{name}: {text}\n"
            payload = payload_text.encode('utf-8')
            broadcast(payload, source_conn=conn)

    except Exception:
        logger.exception('Exception while handling %s', addr)
    finally:
        # Clean up registration
        with clients_lock:
            clients.pop(conn, None)
        try:
            fileobj.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        logger.info('Connection closed %s (%s)', addr, name)


def run_server(host=HOST, port=PORT, max_workers=MAX_WORKERS):
    """Start the echo/broadcast server using a ThreadPoolExecutor."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv, \
         ThreadPoolExecutor(max_workers=max_workers) as pool:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen()
        logger.info('Listening on %s:%d (max_workers=%d)', host, port, max_workers)
        try:
            while True:
                conn, addr = srv.accept()
                pool.submit(handle_client, conn, addr)
        except KeyboardInterrupt:
            logger.info('Server shutting down. Waiting for handlers to finish...')
            pool.shutdown(wait=True)


if __name__ == '__main__':
    run_server()
