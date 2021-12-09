import argparse
from a2dd.a2dd import parse_file, role_parse
from a2dd.utils import yaml_dump


def main():
    """Run script standalone."""
    parser = argparse.ArgumentParser(__doc__)

    parser.add_argument(
        "-r", "--role", dest="role", help="Path to Ansible role"
    )
    parser.add_argument(
        "-f", "--file", dest="file", help="Path to Ansible file"
    )
    args = parser.parse_args()

    if args.role:
        print(yaml_dump(role_parse(role_path=args.role)))
    if args.file:
        print(yaml_dump(parse_file(args.file)))


if __name__ == "__main__":
    main()
