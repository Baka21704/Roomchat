#!/usr/bin/env python3
import sys
import socket
import threading

if sys.version_info[0] < 3:
    print("This script requires Python 3; run with 'python3 client.py'")
    sys.exit(1)

HOST = "127.0.0.1"
PORT = 12345
BUFFER_SIZE = 4096
ENCODING = "utf-8"


def receiver(sock: socket.socket):
    """Background thread: read incoming data line-by-line and print it."""
    # Wrap socket with file-like object to read lines
    try:
        fileobj = sock.makefile('r', encoding=ENCODING, newline='\n')
        for line in fileobj:
            print('\nReceived:', line.rstrip('\n'))
            print('> ', end='', flush=True)
    except Exception as e:
        print('\nReceiver error:', e)


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
            print(f"Connected to {HOST}:{PORT}")
        except Exception as e:
            print("Connection failed:", e)
            return

        # Ask for username and send as first line
        name = input("Enter your name: ").strip() or 'anon'
        try:
            s.sendall((name + '\n').encode(ENCODING))
        except Exception as e:
            print('Failed to send name:', e)
            return

        # Start receiver thread
        t = threading.Thread(target=receiver, args=(s,), daemon=True)
        t.start()

        try:
            while True:
                msg = input("> ")
                if not msg:
                    continue
                if msg.lower() in ("exit", "quit"):
                    print("Closing connection.")
                    break

                # Handle local commands like /nick
                if msg.startswith('/nick '):
                    # send to server so it can notify others
                    s.sendall((msg + '\n').encode(ENCODING))
                    # update local name immediately for UX
                    new = msg.split(' ', 1)[1].strip() if ' ' in msg else ''
                    if new:
                        name = new
                        print(f"You are now known as {name}")
                    continue

                # send message with newline delimiter
                s.sendall((msg + '\n').encode(ENCODING))

        except KeyboardInterrupt:
            print("\nInterrupted, closing.")
        except Exception as e:
            print("Error:", e)

        try:
            s.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass


if __name__ == "__main__":
    main()
