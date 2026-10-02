"""Focused tests for DailyMed SPL section extraction."""

from services.dailymed import _extract_sections
import xml.etree.ElementTree as ET


SAMPLE_SPL = """<?xml version="1.0" encoding="UTF-8"?>
<document xmlns="urn:hl7-org:v3">
  <component>
    <structuredBody>
      <component>
        <section>
          <title>1 INDICATIONS AND USAGE</title>
          <text>
            <paragraph>OZEMPIC is indicated for type 2 diabetes.</paragraph>
          </text>
        </section>
      </component>
      <component>
        <section>
          <title>5 WARNINGS AND PRECAUTIONS</title>
          <text>
            <paragraph>Risk of thyroid C-cell tumors.</paragraph>
          </text>
          <component>
            <section>
              <title>5.1 Thyroid Risk</title>
              <text><paragraph>Contraindicated in MTC.</paragraph></text>
            </section>
          </component>
        </section>
      </component>
      <component>
        <section>
          <title>Empty</title>
          <text></text>
        </section>
      </component>
      <component>
        <section>
          <title>No Text Child</title>
        </section>
      </component>
    </structuredBody>
  </component>
</document>
"""


def test_extract_sections_by_local_tag_ignores_empty():
    root = ET.fromstring(SAMPLE_SPL)
    sections = _extract_sections(root)

    assert sections == [
        {
            "title": "1 INDICATIONS AND USAGE",
            "text": "OZEMPIC is indicated for type 2 diabetes.",
        },
        {
            "title": "5 WARNINGS AND PRECAUTIONS",
            "text": "Risk of thyroid C-cell tumors.",
        },
        {
            "title": "5.1 Thyroid Risk",
            "text": "Contraindicated in MTC.",
        },
    ]
