from __future__ import annotations

from knowledge_extraction.pubmed import parse_pubmed_xml


def test_parse_pubmed_xml_extracts_article_metadata() -> None:
    xml = """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>123</PMID>
          <Article>
            <Journal>
              <Title>Journal of Dental Research</Title>
              <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
            </Journal>
            <ArticleTitle>Dental fluorosis diagnosis</ArticleTitle>
            <Abstract>
              <AbstractText>Dental fluorosis has enamel opaque white spots.</AbstractText>
            </Abstract>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>
    """

    articles = parse_pubmed_xml(xml)

    assert len(articles) == 1
    assert articles[0].pmid == "123"
    assert articles[0].title == "Dental fluorosis diagnosis"
    assert "enamel opaque white spots" in articles[0].abstract
    assert articles[0].journal == "Journal of Dental Research"
    assert articles[0].year == "2024"
