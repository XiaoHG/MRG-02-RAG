"""MRG-02-RAG core package."""

from .catalog import CrawlConfig, SourceSpec, build_sources, default_config, load_config, default_sources
from .crawler import CrawlResult, crawl_sources
from .storage import DatasetWriter
