from ba_downloader.infrastructure.progress.rich_progress import NullProgressReporter


def test_null_progress_reporter_is_noop() -> None:
    reporter = NullProgressReporter()

    with reporter:
        reporter.set_description("Testing")
        reporter.set_total(10)
        reporter.set_completed(3)
        reporter.advance(2)

    reporter.stop()
