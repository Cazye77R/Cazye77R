import json
import os
import sys

STORAGE_FILE = 'solarvolt_data.json'


def load_data():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_data(data):
    with open(STORAGE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def add_entry(key, value):
    data = load_data()
    data[key] = value
    save_data(data)


def list_entries():
    data = load_data()
    if not data:
        print('No entries saved.')
    else:
        for key, value in data.items():
            print(f"{key}: {value}")


def usage():
    print('Usage: python solarvolt.py add <key> <value>')
    print('       python solarvolt.py list')


def main():
    if len(sys.argv) < 2:
        usage()
        return

    command = sys.argv[1]

    if command == 'add' and len(sys.argv) >= 4:
        key = sys.argv[2]
        value = ' '.join(sys.argv[3:])
        add_entry(key, value)
        print(f"Saved {key}: {value}")
    elif command == 'list':
        list_entries()
    else:
        usage()


if __name__ == '__main__':
    main()
