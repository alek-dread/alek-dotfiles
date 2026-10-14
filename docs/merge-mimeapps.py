"""Merge desktop defaults while retaining unrelated user MIME preferences."""
import configparser
from pathlib import Path
import sys


def read(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    with Path(path).open() as stream:
        parser.read_file(stream)
    return parser


def merge(existing, defaults):
    current = read(existing)
    incoming = read(defaults)
    for section in incoming.sections():
        if not current.has_section(section):
            current.add_section(section)
        for mime, value in incoming.items(section):
            if section == "Added Associations":
                entries = value.split(";") + current.get(section, mime, fallback="").split(";")
                value = ";".join(dict.fromkeys(entry for entry in entries if entry)) + ";"
            current.set(section, mime, value)
            if section == "Default Applications" and current.has_option("Removed Associations", mime):
                removed = current.get("Removed Associations", mime).split(";")
                current.set("Removed Associations", mime,
                            ";".join(entry for entry in removed if entry and entry not in value.split(";")) + ";")
    with Path(defaults).open("w") as stream:
        current.write(stream, space_around_delimiters=False)


if __name__ == "__main__":
    merge(*sys.argv[1:])
