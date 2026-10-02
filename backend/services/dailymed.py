import json
import re
import ssl
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi


DAILYMED_SPLS_BASE_URL = (
    "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls"
)


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _element_text(element: ET.Element) -> str:
    return _collapse_whitespace(" ".join(element.itertext()))


def _extract_sections(root: ET.Element) -> list[dict]:
    sections: list[dict] = []
    for section in root.iter():
        if _local_tag(section.tag) != "section":
            continue

        title_el = next(
            (child for child in section if _local_tag(child.tag) == "title"),
            None,
        )
        text_el = next(
            (child for child in section if _local_tag(child.tag) == "text"),
            None,
        )
        if title_el is None or text_el is None:
            continue

        title = _element_text(title_el)
        text = _element_text(text_el)
        if not title or not text:
            continue

        sections.append({"title": title, "text": text})
    return sections


def search_dailymed_labels(drug_name: str, limit: int = 5) -> dict:
    query = drug_name.strip()

    if not query:
        return {
            "status": "error",
            "source": "dailymed",
            "query": query,
            "results": [],
        }

    params = urlencode(
        {
            "drug_name": query,
            "name_type": "both",
            "pagesize": min(max(limit, 1), 10),
            "page": 1,
        }
    )

    request = Request(
        f"{DAILYMED_SPLS_BASE_URL}.json?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "MedRepAI/1.0",
        },
    )

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    try:
        with urlopen(request, timeout=5, context=ssl_context) as response:
            data = json.load(response)
    except HTTPError:
        return {
            "status": "error",
            "source": "dailymed",
            "query": query,
            "results": [],
        }
    except (URLError, TimeoutError, json.JSONDecodeError):
        return {
            "status": "error",
            "source": "dailymed",
            "query": query,
            "results": [],
        }

    results = [
        {
            "setid": item.get("setid"),
            "title": item.get("title"),
            "spl_version": item.get("spl_version"),
            "published_date": item.get("published_date"),
        }
        for item in data.get("data", [])
    ]

    return {
        "status": "ok" if results else "no_results",
        "source": "dailymed",
        "query": query,
        "results": results,
    }


def get_dailymed_label(setid: str) -> dict:
    setid = (setid or "").strip()
    if not setid:
        return {
            "status": "error",
            "source": "dailymed",
            "setid": setid,
            "text": "",
        }

    request = Request(
        f"{DAILYMED_SPLS_BASE_URL}/{setid}.xml",
        headers={
            "Accept": "*/*",
            "User-Agent": "MedRepAI/1.0",
        },
    )
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    try:
        with urlopen(request, timeout=5, context=ssl_context) as response:
            xml_bytes = response.read()
        root = ET.fromstring(xml_bytes)
    except (HTTPError, URLError, TimeoutError, ET.ParseError):
        return {
            "status": "error",
            "source": "dailymed",
            "setid": setid,
            "text": "",
        }

    cleaned_text = _collapse_whitespace(" ".join(root.itertext()))
    sections = _extract_sections(root)

    return {
        "status": "ok",
        "source": "dailymed",
        "setid": setid,
        "text": cleaned_text,
        "sections": sections,
    }
