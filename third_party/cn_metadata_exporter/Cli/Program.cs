namespace YldaDumpCsExporter;

internal static class Program
{
    private static int Main(string[] args)
    {
        try
        {
            var command = (ExportCommand)ExportOptions.Parse(args);
            var profiler = new ExportProfiler(command.Profile);
            return RunExport(command, profiler);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex);
            return 1;
        }
    }

    private static int RunExport(ExportCommand command, ExportProfiler profiler)
    {
        var progress = new ExportProgress();
        var metadataBuffer = ReadAndRestoreMetadata(command.MetadataPath, command.RestoredMetadataOutputPath, command.KeyConstant, profiler, progress, out var usedProtectedRestore);

        progress.Stage("parse metadata", 1, 2);
        var metadata = profiler.Measure("parse", () => YldaMetadataReader.Load(metadataBuffer));
        progress.Stage("build resolved artifact", 2, 2);
        var artifact = profiler.Measure("build resolved artifact", () => new ResolvedExportArtifactBuilder(metadata, profiler, progress).Build());
        progress.Complete();

        var exporter = new YldaDumpExporter(artifact, command.PrivateMembers, command.MethodAddressPlaceholders);
        profiler.Measure("emit", () => exporter.Export(command.OutputPath, command.ImageFilter, command.TypeFilter));
        if (usedProtectedRestore)
            Console.Error.WriteLine("Detected protected metadata and applied restore flow.");
        profiler.Print(Console.Error, "direct-export");
        Console.WriteLine(Path.GetFullPath(command.OutputPath));
        return 0;
    }

    private static byte[] ReadAndRestoreMetadata(
        string metadataPath,
        string? restoredOutputPath,
        uint keyConstant,
        ExportProfiler profiler,
        ExportProgress progress,
        out bool usedProtectedRestore)
    {
        var restoredWasProtected = false;
        progress.Stage("read metadata", 1, 2);
        var metadataBuffer = profiler.Measure("read metadata", () => File.ReadAllBytes(metadataPath));
        progress.Stage("restore metadata", 2, 2);
        metadataBuffer = profiler.Measure("restore", () =>
        {
            if (!YldaMetadataRestorer.LooksProtected(metadataBuffer))
                return metadataBuffer;

            restoredWasProtected = true;
            return YldaMetadataRestorer.Restore(metadataBuffer, keyConstant);
        });

        if (!string.IsNullOrWhiteSpace(restoredOutputPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(restoredOutputPath!)!);
            File.WriteAllBytes(restoredOutputPath!, metadataBuffer);
        }

        progress.Complete();
        usedProtectedRestore = restoredWasProtected;
        return metadataBuffer;
    }
}
