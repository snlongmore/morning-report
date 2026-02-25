"""Tests for the arXiv gatherer and classifier."""

from unittest.mock import patch, MagicMock

import pytest

from morning_report.arxiv.classifier import classify_paper, classify_papers
from morning_report.gatherers.arxiv import ArxivGatherer, _parse_arxiv_entries


class TestClassifier:
    def test_tier2_keyword_match(self):
        result = classify_paper(
            title="Star Formation in the Central Molecular Zone",
            abstract="We study the CMZ...",
            tier2_keywords=["central molecular zone", "CMZ", "star formation"],
            tier3_keywords=["prebiotic"],
        )
        assert result["tier"] == 2
        assert "central molecular zone" in result["matched_keywords"]

    def test_tier3_keyword_match(self):
        result = classify_paper(
            title="Prebiotic molecules in protoplanetary discs",
            abstract="Detection of biosignature gases...",
            tier2_keywords=["CMZ"],
            tier3_keywords=["prebiotic", "biosignature"],
        )
        assert result["tier"] == 3
        assert "prebiotic" in result["matched_keywords"]

    def test_tier1_citation(self):
        result = classify_paper(
            title="Unrelated title",
            abstract="Generic abstract",
            tier2_keywords=["CMZ"],
            tier3_keywords=["prebiotic"],
            citing_bibcodes={"2024arXiv240112345"},
            paper_bibcode="2024arXiv240112345",
        )
        assert result["tier"] == 1

    def test_tier1_takes_precedence(self):
        """Tier 1 should win even if Tier 2 keywords also match."""
        result = classify_paper(
            title="Star Formation in the CMZ",
            abstract="...",
            tier2_keywords=["CMZ", "star formation"],
            tier3_keywords=[],
            citing_bibcodes={"bibcode123"},
            paper_bibcode="bibcode123",
        )
        assert result["tier"] == 1

    def test_no_match(self):
        result = classify_paper(
            title="Dark matter halo profiles",
            abstract="N-body simulations...",
            tier2_keywords=["CMZ"],
            tier3_keywords=["prebiotic"],
        )
        assert result["tier"] is None

    def test_classify_papers_groups_correctly(self):
        papers = [
            {"title": "CMZ star formation", "abstract": "central molecular zone study"},
            {"title": "Prebiotic chemistry", "abstract": "biosignature detection"},
            {"title": "Dark matter haloes", "abstract": "N-body simulations"},
        ]
        tiers = classify_papers(
            papers,
            tier2_keywords=["central molecular zone", "CMZ"],
            tier3_keywords=["prebiotic", "biosignature"],
        )
        assert len(tiers[2]) == 1
        assert len(tiers[3]) == 1
        # Dark matter paper should not appear in any tier
        all_classified = tiers[1] + tiers[2] + tiers[3]
        assert not any("Dark matter" in p["title"] for p in all_classified)


_SAMPLE_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>2</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2602.12345v1</id>
    <title>Star Formation in the Galactic Centre</title>
    <summary>We present new observations of star forming regions in the CMZ.</summary>
    <published>2026-02-25T00:00:00Z</published>
    <updated>2026-02-25T00:00:00Z</updated>
    <author><name>A. Smith</name></author>
    <author><name>B. Jones</name></author>
    <category term="astro-ph.GA" scheme="http://arxiv.org/schemas/atom"/>
    <arxiv:primary_category term="astro-ph.GA"/>
    <arxiv:comment>10 pages, 5 figures</arxiv:comment>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2602.12346v1</id>
    <title>Dark Energy Constraints from BAO</title>
    <summary>We derive new constraints on dark energy.</summary>
    <published>2026-02-25T00:00:00Z</published>
    <updated>2026-02-25T00:00:00Z</updated>
    <author><name>C. Davis</name></author>
    <category term="astro-ph.CO" scheme="http://arxiv.org/schemas/atom"/>
    <category term="astro-ph.GA" scheme="http://arxiv.org/schemas/atom"/>
    <arxiv:primary_category term="astro-ph.CO"/>
  </entry>
</feed>'''


class TestArxivParser:
    def test_parse_entries(self):
        papers = _parse_arxiv_entries(_SAMPLE_XML)
        assert len(papers) == 2

        p0 = papers[0]
        assert p0["arxiv_id"] == "2602.12345"
        assert p0["title"] == "Star Formation in the Galactic Centre"
        assert p0["authors"] == ["A. Smith", "B. Jones"]
        assert p0["primary_category"] == "astro-ph.GA"
        assert p0["comment"] == "10 pages, 5 figures"
        assert p0["abs_url"] == "https://arxiv.org/abs/2602.12345"
        assert p0["pdf_url"] == "https://arxiv.org/pdf/2602.12345"

        p1 = papers[1]
        assert p1["arxiv_id"] == "2602.12346"
        assert p1["primary_category"] == "astro-ph.CO"
        assert "astro-ph.GA" in p1["categories"]


class TestArxivGatherer:
    def test_name(self):
        g = ArxivGatherer()
        assert g.name == "arxiv"

    def test_gather_with_mocked_api(self):
        mock_resp = MagicMock()
        mock_resp.text = _SAMPLE_XML
        mock_resp.raise_for_status = MagicMock()

        with patch("morning_report.gatherers.arxiv.requests.get", return_value=mock_resp), \
             patch("morning_report.gatherers.arxiv.download_pdfs", return_value=1):
            g = ArxivGatherer(
                config={
                    "categories": ["astro-ph.GA"],
                    "tier2_keywords": ["galactic centre", "CMZ", "star formation"],
                    "tier3_keywords": ["prebiotic"],
                    "papers_dir": "/tmp/test_papers",
                },
            )
            result = g.gather()

        assert result["total_new"] == 2
        assert result["tier_counts"]["2"] == 1  # The star formation paper
        assert result["tier_counts"]["3"] == 0
        # Dark energy paper shouldn't match any tier
        assert result["tiers"]["2"][0]["title"] == "Star Formation in the Galactic Centre"
