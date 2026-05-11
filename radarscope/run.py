import argparse
import sys

from radarscope import SerialReader


def main() -> None:
    parser = argparse.ArgumentParser(description="RadarScope – LD2450 frame reader")
    parser.add_argument("--port", default="COM3", help="Serial port (default: COM3)")
    parser.add_argument("--baudrate", type=int, default=256000)
    args = parser.parse_args()

    print(f"Opening {args.port} at {args.baudrate} baud …")

    try:
        with SerialReader(port=args.port, baudrate=args.baudrate) as reader:
            print("Listening for LD2450 frames. Press Ctrl+C to stop.\n")
            while True:
                frame = reader.read_raw_frame()
                if frame:
                    print(frame.hex(" ").upper())
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
