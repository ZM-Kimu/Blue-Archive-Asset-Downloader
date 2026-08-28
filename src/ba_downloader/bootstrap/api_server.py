from __future__ import annotations


def serve_http_api(host: str, port: int | None) -> int:
    from ba_downloader.api.server import ApiBindError, ApiDependencyError, serve

    try:
        from ba_downloader.application.contracts import CatalogRefreshCommand
        from ba_downloader.bootstrap.container import ExecutionScope
        from ba_downloader.domain.models.asset import AssetCollection
        from ba_downloader.domain.models.character import CharacterIndex
        from ba_downloader.domain.models.execution import ExecutionContext
        from ba_downloader.infrastructure.extraction.character.index_store import (
            CharacterIndexFileStore,
            CharacterIndexSearcher,
        )
        from ba_downloader.infrastructure.logging.runtime import get_stdlib_logger

        logger = get_stdlib_logger()

        class IndexLogger:
            def info(self, message: str) -> None:
                logger.info(message)

            def warn(self, message: str) -> None:
                logger.warning(message)

            def error(self, message: str) -> None:
                logger.error(message)

        index_store = CharacterIndexFileStore(IndexLogger())
        index_searcher = CharacterIndexSearcher()

        def load_catalog(
            context: ExecutionContext,
        ) -> tuple[ExecutionContext, AssetCollection]:
            with ExecutionScope(context) as executor:
                result = executor.execute(CatalogRefreshCommand())
            if result.catalog is None:
                raise RuntimeError("Catalog query returned no catalog.")
            return result.context, result.catalog

        def load_character_index(context: ExecutionContext) -> CharacterIndex:
            return index_store.load(context)

        return serve(
            host,
            port,
            catalog_loader=load_catalog,
            character_index_loader=load_character_index,
            character_index_searcher=index_searcher.search,
            log_info=logger.info,
        )
    except (ApiBindError, ApiDependencyError) as exc:
        from ba_downloader.infrastructure.logging.console_logger import ConsoleLogger

        ConsoleLogger().error(str(exc))
        return 1
