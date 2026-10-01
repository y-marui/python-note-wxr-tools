"""Read a note WXR export (ZIP or directory) into plain data."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

NAMESPACES = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "wp": "http://wordpress.org/export/1.2/",
}
ASSETS_PREFIX = "/assets/"


class ExportError(Exception):
    """The input is not a usable note export."""


def qualified(tag: str) -> str:
    """Return the ElementTree tag for a ``prefix:name`` tag."""
    prefix, _, name = tag.rpartition(":")
    return f"{{{NAMESPACES[prefix]}}}{name}" if prefix else name


def prefixed(tag: str) -> str:
    """Return the ``prefix:name`` form of an ElementTree tag."""
    if not tag.startswith("{"):
        return tag
    uri, _, name = tag[1:].partition("}")
    for prefix, known in NAMESPACES.items():
        if known == uri:
            return f"{prefix}:{name}"
    raise ExportError(f"unknown XML namespace: {uri}")


@dataclass
class Item:
    fields: dict[str, str]
    guid_attrs: dict[str, str]


@dataclass
class Export:
    channel: dict[str, str]
    author: dict[str, str]
    items: list[Item] = field(default_factory=list)


class Source:
    """Access to the XML file and the ``assets/`` folder of an export."""

    def __init__(self, path: Path) -> None:
        self._zip: zipfile.ZipFile | None = None
        self._dir: Path | None = None
        if path.is_dir():
            self._dir = path
        elif zipfile.is_zipfile(path):
            self._zip = zipfile.ZipFile(path)
        else:
            raise ExportError(f"not a ZIP file or directory: {path}")

    def _root_xml_names(self) -> list[str]:
        if self._zip is not None:
            names = [n for n in self._zip.namelist() if "/" not in n]
        else:
            assert self._dir is not None
            names = [p.name for p in self._dir.iterdir() if p.is_file()]
        return sorted(n for n in names if n.endswith(".xml"))

    def xml_name(self) -> str:
        names = self._root_xml_names()
        if len(names) != 1:
            raise ExportError(f"expected exactly one XML file, found {len(names)}")
        return names[0]

    def read_xml(self) -> bytes:
        name = self.xml_name()
        if self._zip is not None:
            return self._zip.read(name)
        assert self._dir is not None
        return (self._dir / name).read_bytes()

    def read_asset(self, name: str) -> bytes | None:
        """Return the bytes of ``assets/<name>`` or None if it is absent."""
        if not name or "/" in name or name in (".", ".."):
            return None
        if self._zip is not None:
            try:
                return self._zip.read(f"assets/{name}")
            except KeyError:
                return None
        assert self._dir is not None
        path = self._dir / "assets" / name
        return path.read_bytes() if path.is_file() else None


def parse(xml: bytes) -> Export:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise ExportError(f"invalid XML: {error}") from error
    channel = root.find("channel")
    if channel is None:
        raise ExportError("no <channel> element")
    authors = channel.findall(qualified("wp:author"))
    if len(authors) != 1:
        raise ExportError(f"expected exactly one wp:author, found {len(authors)}")
    export = Export(
        channel={
            prefixed(child.tag): child.text or ""
            for child in channel
            if child.tag not in ("item", qualified("wp:author"))
        },
        author={prefixed(child.tag): child.text or "" for child in authors[0]},
    )
    for element in channel.findall("item"):
        export.items.append(_item(element))
    return export


def _item(element: ElementTree.Element) -> Item:
    fields = {prefixed(child.tag): child.text or "" for child in element}
    guid = element.find("guid")
    return Item(
        fields=fields,
        guid_attrs=dict(guid.attrib) if guid is not None else {},
    )
