#!/usr/bin/env pwsh

param(
    [ValidateSet("all", "smoke", "application", "runtime", "extraction", "regions", "api")]
    [string]$Suite = "all"
)

$ErrorActionPreference = "Stop"

$TestSuites = @{
    application = @(
        "tests/test_application_operations.py"
        "tests/test_asset_filter_service.py"
        "tests/test_asset_workflow.py"
        "tests/test_cli_error_handling.py"
        "tests/test_download_service.py"
        "tests/test_extract_service.py"
        "tests/test_sync_service.py"
        "tests/test_v3_cli.py"
    )
    runtime = @(
        "tests/test_apkpure_protocol.py"
        "tests/test_cancellable_process.py"
        "tests/test_file_operations.py"
        "tests/test_http_client.py"
        "tests/test_package_manager.py"
        "tests/test_process_supervisor.py"
        "tests/test_resource_downloader.py"
        "tests/test_runtime_snapshots.py"
        "tests/test_zip_range_reader.py"
    )
    extraction = @(
        "tests/test_assetripper_bundles.py"
        "tests/test_assetripper_dependencies.py"
        "tests/test_assetripper_dotnet.py"
        "tests/test_assetripper_entry_store.py"
        "tests/test_assetripper_exporter.py"
        "tests/test_assetripper_scheduler.py"
        "tests/test_character_index.py"
        "tests/test_character_index_contract.py"
        "tests/test_dump_backend.py"
        "tests/test_encryption.py"
        "tests/test_flatbuffer_codegen.py"
        "tests/test_media_extractor.py"
        "tests/test_memorypack_codegen.py"
        "tests/test_process_table_runner.py"
        "tests/test_schema_architecture.py"
        "tests/test_schema_snapshots.py"
        "tests/test_sqlcipher_exporter.py"
        "tests/test_table_components.py"
        "tests/test_table_extractor.py"
    )
    regions = @(
        "tests/test_cn_metadata_recovery_pipeline.py"
        "tests/test_jp_runtime_assets.py"
        "tests/test_jp_server.py"
        "tests/test_jp_table_metadata_manifest.py"
        "tests/test_provider_results.py"
        "tests/test_region_registry.py"
    )
    api = @(
        "tests/test_api_contexts.py"
        "tests/test_api_contract.py"
        "tests/test_api_events.py"
        "tests/test_api_files.py"
        "tests/test_api_jobs.py"
        "tests/test_api_packaging.py"
        "tests/test_api_server.py"
        "tests/test_api_worker.py"
    )
    smoke = @(
        "tests/test_v3_cli.py"
        "tests/test_application_operations.py"
        "tests/test_region_registry.py"
        "tests/test_asset_workflow.py"
    )
}

if ($Suite -eq "all") {
    $TestPaths = @(
        $TestSuites.application
        $TestSuites.runtime
        $TestSuites.extraction
        $TestSuites.regions
        $TestSuites.api
    )
} else {
    $TestPaths = $TestSuites[$Suite]
}

Write-Host "Running $Suite test suite ($($TestPaths.Count) modules)..." -ForegroundColor Cyan
& uv run pytest -q @TestPaths
if ($LASTEXITCODE -ne 0) {
    throw "$Suite test suite failed with exit code $LASTEXITCODE."
}
