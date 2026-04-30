import pyshark
import subprocess


def start_capture():
    """Launch tshark and return its combined stdout/stderr output."""
    stdout = subprocess.run(
        [r'"C:\Program Files\Wireshark\tshark" -i 5"'],
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout
    stdout.decode()
    print(stdout)


def capture_parse():
    """Placeholder for parsing packets from the capture stream."""
    pass


if __name__ == "__main__":
    start_capture()
